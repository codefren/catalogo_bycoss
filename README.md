# Catálogo de datos (PostgreSQL) para Databricks

Base de datos independiente para consultar y actualizar un catálogo (~250k filas,
2 tablas) desde Databricks por JDBC.

## Levantar la DB

```bash
cp .env.example .env          # pon una contraseña fuerte
docker compose up -d
docker compose logs -f postgres
```

El esquema de `initdb/01_schema.sql` se aplica **solo la primera vez** (cuando el
volumen está vacío). Adáptalo a tus 2 tablas antes del primer arranque.

---

## El DNS: cómo funciona aquí (importante)

Postgres **no pasa por el reverse proxy (Caddy)**. Caddy enruta HTTP por nombre de
dominio (cabecera `Host`), pero Postgres es un protocolo TCP crudo que no lleva esa
cabecera: no se puede enrutar por hostname como las webs. Databricks se conecta por
`IP:puerto` directo, exactamente igual que ya haces con el SQL Server de Arsys
(`82.223.100.253:4313`).

Entonces, "ponerle DNS a la DB" = crear un registro **A** que apunte a la IP del VPS.
El nombre es solo una comodidad para no escribir la IP; el enrutado sigue siendo por
IP y puerto.

### 1. Registro DNS
En tu proveedor de DNS, crea un registro A:

```
db-catalogo.tudominio.com   A   <IP_PUBLICA_DEL_VPS>
```

(No necesita HTTPS ni Caddy. No pongas CNAME hacia los dominios de TimeShift.)

### 2. Abrir el puerto en el firewall — restringido

Exponer Postgres a todo internet es peligroso. Ábrelo **solo a las IPs de salida de
Databricks** (las de tu workspace; en AWS/Azure son el NAT del workspace — búscalas en
la consola de Databricks o pídelas a tu admin). Con `ufw`:

```bash
# Repite por cada IP/rango de salida de tu workspace de Databricks:
sudo ufw allow from <IP_DATABRICKS> to any port 5432 proto tcp
```

Si tu VPS es Arsys y el firewall es externo (como con el 4313 actual), aplica ahí la
misma regla: permitir el puerto solo desde las IPs de Databricks.

> Docker publica el puerto saltándose `ufw` en algunos setups. Verifica desde fuera con
> `nc -vz <IP> 5432`; si responde sin estar tú en la allowlist, restringe en el firewall
> del proveedor o publica el puerto solo en una IP concreta.

---

## Conectar desde Databricks

Driver `org.postgresql.Driver` ya viene en el runtime de Databricks.

```python
jdbc_hostname = "db-catalogo.tudominio.com"   # o la IP directa
jdbc_port     = 5432
database      = "catalogo"
user          = "catalogo"
password      = dbutils.secrets.get("scope", "catalogo_pwd")  # no lo pongas en claro

jdbc_url = (
    f"jdbc:postgresql://{jdbc_hostname}:{jdbc_port}/{database}"
    f"?sslmode=require"          # exige canal cifrado (ver TLS abajo)
)

def leer(dbtable):
    return (
        spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", dbtable)
        .option("user", user)
        .option("password", password)
        .load()
    )

df = leer("articulos")
display(df)
```

### Actualizar el catálogo (upsert rápido)

Escribe por **lotes** a una tabla staging y haz el upsert en Postgres con
`INSERT ... ON CONFLICT`. A 250k filas lo caro es el round-trip, no el UPDATE.

```python
(df_nuevo.write.format("jdbc")
    .option("url", jdbc_url)
    .option("dbtable", "articulos_stg")
    .option("user", user).option("password", password)
    .option("batchsize", 5000)
    .option("numPartitions", 4)
    .mode("overwrite")
    .save())
```

Luego, una sola sentencia (vía psql, un job, o `foreachPartition`):

```sql
INSERT INTO articulos AS a (id, codigo, descripcion, categoria, actualizado)
SELECT id, codigo, descripcion, categoria, now() FROM articulos_stg
ON CONFLICT (id) DO UPDATE SET
    codigo      = EXCLUDED.codigo,
    descripcion = EXCLUDED.descripcion,
    categoria   = EXCLUDED.categoria,
    actualizado = now();
```

---

## TLS de Postgres (recomendado si lo expones a internet)

Por defecto el servidor no fuerza TLS. Para cifrar el tráfico puedes montar un
certificado (aunque sea autofirmado) y arrancar Postgres con `ssl=on`; con
`sslmode=require` en Databricks basta para cifrar sin verificar CA. Pídemelo y te
dejo la variante del compose con TLS.

---

# API para terceros (FastAPI, servicio `api`)

Para exponer el catálogo a **terceros por HTTP** hay un servicio `api` (solo
lectura) delante de Postgres. A diferencia de Postgres, esto **sí** va detrás de
Caddy (es HTTP y se enruta por dominio).

Reparto de responsabilidades:
- **Terceros** → HTTPS → Caddy → `api` (solo GET, con API key).
- **Databricks** → JDBC directo a Postgres (consulta y actualiza). No pasa por la API.

## Seguridad incluida
- **API key** en cabecera `X-API-Key` (comparación en tiempo constante).
- **CORS** restringido a `CORS_ORIGINS` (nunca `*`).
- **Rate limiting** por IP (`RATE_LIMIT`).
- **Consultas parametrizadas** (sin inyección SQL).
- **Solo GET**: los terceros no pueden escribir.
- Contenedor como **usuario sin privilegios**.

## Conectar la API a Caddy (reverse proxy)

El `api` y Caddy están en **compose distintos**, así que comparten una red Docker
externa. Una sola vez en el VPS:

```bash
docker network create edge
```

En el compose de **TimeShift** (`docker-compose.cluster.yml`), añade `edge` a las
redes del servicio `caddy` y decláralas como externa:

```yaml
  caddy:
    networks: [timeshift-web, edge]

networks:
  edge:
    external: true
```

En el **Caddyfile** de TimeShift (`docker/Caddyfile`), añade el sitio nuevo:

```caddy
catalogo.tudominio.com {
	reverse_proxy databricks-catalog-api:8000
	encode gzip zstd
}
```

Recarga Caddy sin downtime:

```bash
docker exec tsz-caddy caddy reload --config /etc/caddy/Caddyfile
```

Y el DNS: registro **A** `catalogo.tudominio.com → IP_del_VPS` (igual que los
dominios de TimeShift). Caddy emite el certificado Let's Encrypt solo.

## Levantar este stack (Postgres + API)

```bash
docker compose up -d --build
```

## Probar la API

```bash
# Falla sin clave (401):
curl https://catalogo.tudominio.com/api/articulos

# Con clave:
curl -H "X-API-Key: TU_CLAVE" "https://catalogo.tudominio.com/api/articulos?limit=10"
curl -H "X-API-Key: TU_CLAVE" "https://catalogo.tudominio.com/api/articulos/123"
```

Docs OpenAPI (si quieres dejarlas públicas): `https://catalogo.tudominio.com/docs`.

