# Autenticación de la Catálogo API

La API es de **solo lectura** y protege todos los endpoints `/api/*` con **JWT**.
Los usuarios viven en la base de datos (tabla `api_users`, contraseña con hash
**bcrypt**). El flujo es: **login → access token (JWT, 12 h) + refresh token
(opaco, 7 d) → renovar con el refresh → logout**.

- Swagger (UI interactiva): `https://bycos.data4tex.com/docs`
- ReDoc: `https://bycos.data4tex.com/redoc`
- OpenAPI: `https://bycos.data4tex.com/openapi.json`

---

## 1. Modelo de autenticación

| Token | Qué es | Caducidad | Dónde se usa |
|-------|--------|-----------|--------------|
| `access_token` | JWT firmado (HS256), `sub` = usuario | **12 h** (`ACCESS_TOKEN_EXPIRE_HOURS`) | cabecera `Authorization: Bearer <token>` en `/api/*` |
| `refresh_token` | Secreto opaco aleatorio | **7 d** (`REFRESH_TOKEN_EXPIRE_DAYS`) | cuerpo de `/auth/refresh` y `/auth/logout` |

Notas de seguridad:

- Las contraseñas se guardan como **hash bcrypt**, nunca en claro.
- De los refresh tokens solo se guarda su **hash SHA-256** (tabla
  `api_refresh_tokens`); son **revocables**.
- `/auth/refresh` aplica **rotación**: al renovar, el refresh usado queda
  revocado y se emite uno nuevo. Reusar uno viejo devuelve `401`.
- El `access_token` se valida solo por firma + caducidad: si desactivas o borras
  un usuario, su access token sigue válido **hasta que caduque** (máx. 12 h); su
  refresh token, en cambio, deja de poder renovar en cuanto el usuario está
  inactivo.

---

## 2. Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/auth/token` | usuario + contraseña (form) | Login. Devuelve access + refresh. |
| `POST` | `/auth/refresh` | refresh token (JSON) | Renueva el access (y rota el refresh). |
| `POST` | `/auth/logout` | refresh token (JSON) | Revoca el refresh token. |
| `GET`  | `/api/skus`, `/api/skus/{sku}` | Bearer | Catálogo (tabla `sku`). |
| `GET`  | `/api/ventas`, `/api/ventas/ticket/...` | Bearer | Ventas (tabla `ticket_maestro`). |
| `GET`  | `/health` | — | Salud del servicio (sin auth). |

Todos los `/api/*` y los `/auth/*` están sujetos al **rate limit** por IP
(`RATE_LIMIT`, por defecto `60/minute`); al superarlo responden `429`.

---

## 3. Uso (cliente)

```bash
BASE=https://bycos.data4tex.com

# 1) Login: usuario + contraseña (form-urlencoded)
curl -s -X POST "$BASE/auth/token" \
  -d 'username=bycos&password=TU_CONTRASEÑA'
# -> {"access_token":"...","token_type":"bearer","expires_in":43200,
#     "refresh_token":"...","refresh_expires_in":604800}

# 2) Llamar a un endpoint con el access token
curl -s "$BASE/api/skus?limit=2" \
  -H "Authorization: Bearer EL_ACCESS_TOKEN"

# 3) Renovar cuando el access caduque (sin volver a enviar la contraseña)
curl -s -X POST "$BASE/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"EL_REFRESH_TOKEN"}'
# -> nuevos access_token y refresh_token (el anterior queda revocado)

# 4) Cerrar sesión (revoca el refresh)
curl -s -X POST "$BASE/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"EL_REFRESH_TOKEN"}'
```

En **Swagger** (`/docs`): pulsa **Authorize**, introduce usuario y contraseña, y
ya puedes probar los endpoints protegidos.

---

## 4. Gestión de usuarios

Los usuarios se crean con el script `api/create_user.py`, que se ejecuta **dentro
del contenedor** de la API. El script crea la tabla `api_users` si no existe, así
que funciona también sobre una base ya desplegada.

### Crear o actualizar un usuario

```bash
docker compose exec api python create_user.py <usuario> '<contraseña>'
```

- Si el usuario ya existe, **actualiza su contraseña**.
- Para crearlo desactivado, añade `--inactivo`.

### Ejemplo: usuario `bycos`

```bash
# Genera una contraseña fuerte (opcional):
openssl rand -base64 24

# Crea el usuario bycos:
docker compose exec api python create_user.py bycos 'LA_CONTRASEÑA_QUE_GENERES'
```

Luego comprueba que puede autenticarse:

```bash
curl -s -X POST https://bycos.data4tex.com/auth/token \
  -d 'username=bycos&password=LA_CONTRASEÑA_QUE_GENERES'
```

Debe devolver un `access_token` y un `refresh_token`.

### Desactivar un usuario

Vuelve a crearlo con `--inactivo` (conserva la contraseña si pasas la misma, o
ponle una nueva):

```bash
docker compose exec api python create_user.py bycos 'CUALQUIERA' --inactivo
```

> Nota: un usuario desactivado ya no puede hacer login ni renovar; su access
> token vigente seguirá valiendo hasta que caduque (máx. 12 h).

---

## 5. Configuración (variables de entorno)

| Variable | Obligatoria | Por defecto | Descripción |
|----------|-------------|-------------|-------------|
| `JWT_SECRET` | **Sí** | — | Secreto para firmar los JWT. Genera: `openssl rand -hex 32`. |
| `ACCESS_TOKEN_EXPIRE_HOURS` | No | `12` | Caducidad del access token (horas). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Caducidad del refresh token (días). |
| `RATE_LIMIT` | No | `60/minute` | Límite de peticiones por IP (formato slowapi). |
| `CORS_ORIGINS` | No | vacío | Orígenes CORS permitidos (coma). Nunca `*` en prod. |
| `DATABASE_URL` | **Sí** | — | Conexión a Postgres (`postgresql+asyncpg://...`). |

Las tablas `api_users` y `api_refresh_tokens` se crean automáticamente al
arrancar la API (no requieren migración manual).
