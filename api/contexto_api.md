# Catálogo API — contexto completo para asistentes (LLM)

> Documento pensado para dárselo a Claude u otro asistente como contexto. Explica
> qué datos hay, cómo autenticarse, cada endpoint con sus filtros y campos, cómo
> se relacionan las tablas y qué trampas evitar. Contrato técnico exacto (tipos,
> validaciones): `/openapi.json`. UI interactiva: `/docs`.

## 1. Qué es

API HTTP **de solo lectura** (solo `GET` sobre datos) del catálogo de una cadena
de tiendas de moda. Expone cinco conjuntos de datos que vienen del ERP:

| Recurso | Ruta base | Tabla | Grano (qué es una fila) |
|---|---|---|---|
| Catálogo / stock | `/api/skus` | `sku` | Un SKU (artículo + color + talla) **en un almacén** |
| Stock por almacén | `/api/stock` | `stock` | Un artículo-color-talla **en un almacén**, con la descripción del almacén |
| Almacenes | `/api/stock/almacenes` | `stock` agregada | Un almacén con su descripción |
| Ventas (líneas) | `/api/ventas` | `ticket_maestro` | Una **línea** de ticket |
| Ventas (cabeceras) | `/api/ventas/cabeceras` | `ticket_maestro` agregada | Un **ticket** con sus totales |
| Compras | `/api/compras` | `compras_maestro` | Un artículo-color-talla comprado a un proveedor |
| Cajas pendientes | `/api/cajas-pendientes` | `cajas_pendientes` | Un artículo-color-talla dentro de una caja en tránsito a tienda |

- Base URL de producción: `https://bycos.data4tex.com`
- Formato: JSON (UTF-8). Nombres de campo en español; muchos con prefijo `fld`
  heredado del ERP (`fldIdArticulo`, `fldTemporada`, …). Respeta mayúsculas.
- No hay endpoints de escritura: no se puede crear, modificar ni borrar nada.

## 2. Autenticación (JWT)

Todos los `/api/*` exigen `Authorization: Bearer <access_token>`.

1. **Login** — `POST /auth/token`, cuerpo **form-urlencoded** (no JSON):
   `username=<usuario>&password=<contraseña>`.
   Respuesta:
   ```json
   {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 43200,
    "refresh_token": "Xq3f9...", "refresh_expires_in": 604800}
   ```
   `access_token` dura **12 h**; `refresh_token` dura **7 días**.
2. **Renovar** — `POST /auth/refresh`, cuerpo JSON `{"refresh_token": "..."}`.
   Devuelve un par nuevo con la misma forma. **Rotación**: el refresh usado
   queda revocado; guarda siempre el nuevo. Reusar uno viejo → `401`.
3. **Logout** — `POST /auth/logout`, cuerpo JSON `{"refresh_token": "..."}`.
   Revoca el refresh (el access sigue valiendo hasta caducar).

Si una llamada a `/api/*` devuelve `401` con `"Token expirado"`, renueva con el
refresh y repite. Si el refresh también da `401`, vuelve a hacer login.

`GET /health` (sin auth) → `{"status": "ok"}`.

## 3. Convenciones comunes

### Sobre paginado
Los listados devuelven:
```json
{"items": [ ... ], "count": 50, "limit": 50, "offset": 0}
```
- `limit`: tamaño de página, **1–500**, por defecto 50.
- `offset`: desplazamiento, ≥ 0.
- `count`: nº de filas **de esta página** (NO el total de la consulta). No hay
  total disponible.
- **Para leerlo todo**: pide páginas con `limit=500` y `offset` += 500 hasta que
  `count < limit`. Todos los listados tienen orden total (el `ORDER BY` acaba
  en una clave única), así que no se repiten ni saltan filas
  mientras los datos no cambien.

### Filtros
- Todos son opcionales y van en la query string. Varios filtros distintos se
  combinan con **AND**.
- Salvo que se diga lo contrario, la comparación es **igualdad exacta** de texto
  (sensible a mayúsculas y a ceros a la izquierda: `00000207` ≠ `207`).
- Fechas en `YYYY-MM-DD`; rangos `fecha_desde`/`fecha_hasta` son **inclusivos**
  e independientes (puedes usar uno solo).
- Textos de filtro: máx. 50 caracteres (salvo donde se indique).

### Valores nulos
Casi todas las columnas pueden venir `null` (la base no las declara NOT NULL).
Trata cualquier campo como opcional.

### Errores
| Código | Cuándo | Cuerpo |
|---|---|---|
| `401` | Falta token, token inválido/expirado, login incorrecto | `{"detail": "..."}` |
| `404` | Recurso concreto inexistente (SKU, ticket, caja) | `{"detail": "..."}` |
| `422` | Parámetro inválido (tipo, rango, valor no permitido) | `{"detail": [ ... ]}` o `{"detail": "..."}` |

### Uso recomendado
Hasta **1080 peticiones por minuto**. Prefiere pocas peticiones con `limit=500`
y filtros precisos antes que muchas pequeñas.

## 4. Modelo de datos y relaciones

Claves comunes entre recursos (son texto, compáralas tal cual):

| Concepto | sku | stock | ventas | compras | cajas pendientes |
|---|---|---|---|---|---|
| SKU | `sku` | — | `sku` | — | — |
| Artículo | `fldIdArticulo` | `fldIdArticulo` | `fldIdArticulo` | `fldIdArticulo` | `articulo` |
| Color | `fldIdColor` | `fldIdColor` | `fldIdColor` | `fldIdColor` | `color` |
| Talla | `talla` | `talla` | `fldTalla` | `talla` | `talla` |
| Almacén / tienda | `fldIdAlmacen` | `fldIdAlmacen` | `fldIdAlmacen` | `fldIdAlmacen` | `tienda` |
| Código de barras | `codigo_barras` | — | — | — | `ean` |
| Temporada | `fldTemporada` | — | — | `fldTemporada` | — |
| Familia | `fldIdFamilia` | — | — | `fldIdFamilia` | `familia` |
| Marca | `fldIdMarca` | — | — | — | `marca` |

- Un **artículo** tiene varias **permutas** color/talla; cada permuta es un
  **SKU**. Formato habitual del SKU: `<articulo>-<color>-<talla>`
  (p. ej. `0100228002-000005-U`), pero no lo construyas a mano: búscalo.
- Un **ticket** se identifica por la clave natural
  **(`fldIdEmpresa`, `fldIdAlmacen`, `fldIdCaja`, `fldIdTicket`)**; `fldIdTicket`
  solo NO es único entre tiendas/cajas.
- La **descripción del almacén** solo está en `stock` (`almacen_descripcion`).
  Para el nombre de un `fldIdAlmacen` de cualquier recurso, usa
  `GET /api/stock/almacenes`.

## 5. Endpoints

### 5.1 Catálogo — `GET /api/skus`

Una fila por **SKU y almacén**: el mismo SKU aparece una vez por cada almacén
que lo tiene. Para el stock total de un SKU, **suma** `stock_disponible` de sus
filas.

**Campos** (`items[]`):

| Campo | Tipo | Descripción |
|---|---|---|
| `sku` | string | Código de SKU (artículo-color-talla). |
| `fldIdAlmacen` | string | Almacén/tienda de esta fila. |
| `fldIdArticulo` | string | Código de artículo. |
| `articulo_descripcion` | string | Descripción del artículo. |
| `fldTemporada` | string | Temporada (p. ej. `V25`, `I25`). |
| `fldIdFamilia` | string | Código de familia. |
| `fldIdSexo` | string | Código de sexo (solo código, sin descripción). |
| `fldReferencia` | string | Referencia del proveedor/fabricante. |
| `codigo_barras` | string | EAN de la **talla concreta** (AECOC); si esa talla no tiene EAN, el del artículo. |
| `fldColeccion` | string | Colección. |
| `fldIdMarca` | string | Código de marca. |
| `fldIdColor` | string | Código de color. |
| `color_descripcion` | string | Descripción del color. |
| `fldIdGrupoTallas` | string | Código del grupo de tallas. |
| `grupotalla_descripcion` | string | Descripción del grupo de tallas. |
| `talla` | string | Talla. |
| `pvp` | number | Precio de venta al público (con IVA). |
| `precio_costo` | number | Coste unitario **actual** (sin histórico; sin IVA). |
| `total_transito` | number | Unidades **en tránsito** (pedidas, aún no recibidas en el almacén). |
| `stock_disponible` | number | Stock disponible **en este almacén**. |
| `actualizado_en` | datetime | Última actualización (sin zona horaria). |

No se exponen (no los pidas ni los inventes): proveedor, mínimos/máximos de
stock, punto de pedido, totales de entradas/salidas.

**Filtros**. Los marcados *(rep.)* aceptan **varios valores** repitiendo el
parámetro (`?almacen=A&almacen=B`), combinados con **OR**, máx. 50 valores.

| Parámetro | Columna | Notas |
|---|---|---|
| `q` | `articulo_descripcion` | Contiene el texto, sin distinguir mayúsculas (máx. 200). |
| `sku_prefijo` | `sku` | SKUs que empiezan por este texto (máx. 100). |
| `almacen` *(rep.)* | `fldIdAlmacen` | |
| `articulo` *(rep.)* | `fldIdArticulo` | Devuelve todas sus permutas color/talla. |
| `temporada` *(rep.)* | `fldTemporada` | |
| `familia` *(rep.)* | `fldIdFamilia` | |
| `sexo` *(rep.)* | `fldIdSexo` | |
| `marca` *(rep.)* | `fldIdMarca` | |
| `coleccion` *(rep.)* | `fldColeccion` | |
| `color` *(rep.)* | `fldIdColor` | |
| `grupo_tallas` *(rep.)* | `fldIdGrupoTallas` | |
| `talla` *(rep.)* | `talla` | |
| `codigo_barras` *(rep.)* | `codigo_barras` | |
| `referencia` *(rep.)* | `fldReferencia` | |
| `pvp_min`, `pvp_max` | `pvp` | Inclusivos; `pvp_min > pvp_max` → 422. |
| `stock_min`, `stock_max` | `stock_disponible` | Inclusivos. |
| `con_stock` | `stock_disponible` | `true` → solo filas con stock > 0. |
| `actualizado_desde` | `actualizado_en` | ISO 8601 (`2025-10-14T00:00:00`). Para sincronización incremental. |
| `orden` | — | `sku` (defecto), `articulo`, `pvp`, `stock`, `actualizado`. |
| `direccion` | — | `asc` (defecto) o `desc`. Los nulos van siempre al final. |
| `limit`, `offset` | — | Paginación. |

### 5.2 Catálogo — `GET /api/skus/{sku}`

Las filas de **un** SKU, una por almacén, ordenadas por almacén, en el mismo
sobre paginado. Filtro opcional `almacen` *(rep.)*. `404` si no existe.

### 5.3 Stock — `GET /api/stock`

Una fila por **artículo-color-talla y almacén**, con la **descripción del
almacén**. `stock_disponible` es el stock de ese almacén y **puede ser
negativo**. Para totales, **suma** `stock_disponible` de las filas.

**Campos** (`items[]`):

| Campo | Tipo | Descripción |
|---|---|---|
| `fldIdAlmacen` | string | Código de almacén/tienda. |
| `almacen_descripcion` | string | Nombre del almacén/tienda. |
| `fldIdArticulo` | string | Código de artículo. |
| `fldIdColor` | string | Código de color. |
| `talla` | string | Talla. |
| `total_transito` | number | Unidades **en tránsito** (pedidas, aún no recibidas en el almacén). |
| `stock_disponible` | number | Stock disponible **en este almacén** (puede ser negativo). |
| `actualizado_en` | datetime | Última actualización (sin zona horaria). |

No trae descripción de artículo ni de color, ni PVP: para eso cruza con
`/api/skus?articulo=X`. No se exponen los totales de entradas/salidas/servicio/tránsito.

**Filtros**:

| Parámetro | Columna | Notas |
|---|---|---|
| `almacen` *(rep.)* | `fldIdAlmacen` | |
| `almacen_nombre` | `almacen_descripcion` | Contiene el texto, sin distinguir mayúsculas (máx. 200). |
| `articulo` *(rep.)* | `fldIdArticulo` | |
| `color` *(rep.)* | `fldIdColor` | |
| `talla` *(rep.)* | `talla` | |
| `stock_min`, `stock_max` | `stock_disponible` | Inclusivos; `stock_min > stock_max` → 422. |
| `con_stock` | `stock_disponible` | `true` → solo filas con stock > 0. |
| `actualizado_desde` | `actualizado_en` | ISO 8601. Para sincronización incremental. |
| `orden` | — | `almacen` (defecto), `articulo`, `stock`, `actualizado`. |
| `direccion` | — | `asc` (defecto) o `desc`. Los nulos van siempre al final. |
| `limit`, `offset` | — | Paginación. |

### 5.4 Almacenes — `GET /api/stock/almacenes`

Lista **completa** (sin paginar) de almacenes: `fldIdAlmacen` y
`almacen_descripcion`, ordenados por código. Úsala para poner nombre a un
`fldIdAlmacen` de cualquier otro endpoint.

Algunos almacenes no tienen descripción y vienen con `almacen_descripcion: null`
(p. ej. `00000000`, `00000036`, `00000999`, `00001234`): muestra el código.

### 5.5 Ventas — `GET /api/ventas`

Una fila por **línea de ticket**. Orden: fecha desc, ticket, línea, empresa, almacén, caja.

**Campos**: `fldIdEmpresa`, `fldIdAlmacen`, `fldIdCaja`, `fldIdTicket`,
`fldLinea` (string); `fecha` (date); `fldHora` (string `HH:MM:SS`);
`fldIdCliente`, `fldIdMoneda` (string); `fldCambio` (number);
`fldIdArticulo`, `fldIdColor`, `fldTalla`, `sku` (string);
`fldCantidad`, `fldPrecio`, `dto_linea`, `importe_linea`, `fldIVA` (number);
`actualizado_en` (datetime).

- `importe_linea` es el importe de la línea; `fldPrecio` el unitario.

**Filtros**: `fecha_desde`, `fecha_hasta`, `almacen`, `ticket`, `sku` (máx. 100),
`cliente`, `limit`, `offset`. Un solo valor por filtro.

### 5.6 Ventas — `GET /api/ventas/ticket/{empresa}/{almacen}/{caja}/{ticket}`

Todas las líneas de un ticket por su clave natural, ordenadas por línea. Mismo
sobre paginado y campos que 5.5. `404` si no hay líneas.

### 5.7 Ventas — `GET /api/ventas/cabeceras`

Una fila por **ticket** con sus totales (sin duplicarlos por línea). Úsalo para
importes por ticket, nº de tickets, ticket medio, etc. Orden: fecha desc, ticket, empresa, almacén, caja.

**Campos**: clave natural (`fldIdEmpresa`, `fldIdAlmacen`, `fldIdCaja`,
`fldIdTicket`), `fecha`, `fldHora`, `fldIdCliente`, `fldIdMoneda`, `fldCambio`,
y totales: `fldPrendas`, `fldImporteBruto`, `fldImporteDto`, `fldImporteNeto`,
`fldCobradoTicket`, `fldPteTicket`, `dto_cabecera`, `fldCupones`, `fldEspecial`
(number); `fldVales`, `fldApartados`, `fldArreglos`, `fldPromociones`,
`fldChequeRegalo` (integer, recuentos).

**Filtros**: `fecha_desde`, `fecha_hasta`, `almacen`, `cliente`, `ticket`,
`limit`, `offset`.

### 5.8 Ventas — `GET /api/ventas/cabecera/{empresa}/{almacen}/{caja}/{ticket}`

La cabecera de un ticket. **Devuelve un objeto suelto** (no sobre paginado) con
los campos de 5.7. `404` si no existe.

### 5.9 Compras — `GET /api/compras`

Una fila por artículo-color-talla comprado. Orden: fecha desc, proveedor,
artículo, color, posición de talla, almacén.

**Campos**: `fldIdEmpresa`, `fldIdAlmacen`, `fldIdProveedor`, `nombre_proveedor`
(string); `fecha` (date); `fldIdArticulo`, `fldIdColor` (string); `talla_pos`
(integer, posición de la talla en su grupo); `talla` (string); `cantidad`
(number); `fldIdMoneda` (string); `fldCambio` (number); `descripcion_articulo`,
`fldTemporada`, `fldIdFamilia`, `fldIdGrupoTallas`, `descripcion_grupo_tallas`
(string).

**Filtros**: `fecha_desde`, `fecha_hasta`, `almacen`, `proveedor`, `articulo`,
`color`, `talla`, `temporada`, `familia`, `limit`, `offset`.

### 5.10 Cajas pendientes — `GET /api/cajas-pendientes`

Mercancía enviada a tienda que **aún no ha llegado**. Una fila por
artículo-color-talla dentro de una caja. Claves en **snake_case**. Orden: fecha
de salida desc, caja, artículo, color, talla.

**Campos**: `cod_cliente`, `tienda`, `nombre_tienda`, `dispatch_note` (albarán),
`fecha_salida`, `fecha_llegada`, `codigo_caja`, `no_bulto` (string);
`total_prendas` (integer, prendas de toda la caja); `no_pedido`, `no_envio`,
`ean`, `articulo`, `color`, `talla`, `descripcion_articulo`, `descripcion_color`,
`marca`, `familia`, `descripcion_familia` (string); `cantidad` (integer, de esta
línea).

- `fecha_salida` y `fecha_llegada` son **texto** tal cual viene del origen (no
  hay filtro por fecha). No asumas el formato sin mirar un ejemplo.
- `total_prendas` se repite en todas las líneas de la caja: **no lo sumes** entre
  líneas; para unidades suma `cantidad`.

**Filtros**: `tienda`, `cliente`, `articulo`, `ean`, `caja`, `pedido`, `envio`,
`dispatch_note`, `limit`, `offset`.

### 5.11 Cajas pendientes — `GET /api/cajas-pendientes/caja/{codigo_caja}`

Todas las líneas de una caja, ordenadas por artículo, color y talla. `404` si no hay.

## 6. Recetas para preguntas habituales

| Pregunta | Cómo |
|---|---|
| ¿Cuánto stock hay del artículo X en la tienda T? | `GET /api/skus?articulo=X&almacen=T` → una fila por color/talla; suma `stock_disponible`. |
| ¿Stock de un artículo por tienda, con el nombre de la tienda? | `GET /api/stock?articulo=X&limit=500` → una fila por color/talla y tienda, con `almacen_descripcion`. |
| ¿Cómo se llama la tienda T? | `GET /api/stock/almacenes` → busca `fldIdAlmacen = T`. |
| ¿Stock total de un SKU en todas las tiendas? | `GET /api/skus/{sku}` → suma `stock_disponible` de `items`. |
| ¿Qué tallas/colores tiene un artículo? | `GET /api/skus?articulo=X&limit=500` → valores distintos de `fldIdColor`/`talla`. |
| ¿A qué producto corresponde un código de barras? | `GET /api/skus?codigo_barras=EAN` |
| ¿Unidades vendidas de un SKU en un periodo? | `GET /api/ventas?sku=S&fecha_desde=…&fecha_hasta=…`, paginando; suma `fldCantidad`. |
| ¿Facturación de una tienda en un mes? | `GET /api/ventas/cabeceras?almacen=T&fecha_desde=…&fecha_hasta=…`, paginando; suma `fldImporteNeto`. Nº de tickets = nº de filas. |
| ¿Qué se compró a un proveedor? | `GET /api/compras?proveedor=P&fecha_desde=…` |
| ¿Qué le llega a una tienda? | `GET /api/cajas-pendientes?tienda=T&limit=500`; agrupa por `codigo_caja`. |
| ¿Viene en camino un producto? | `GET /api/cajas-pendientes?ean=EAN` (o `articulo=X`). |
| ¿Margen de un periodo? | Líneas de `/api/ventas` + `precio_costo` de `/api/skus` (cruza por almacén, artículo, color y talla; en ventas `fldTalla`). Venta sin IVA = `importe_linea / (1 + fldIVA/100)`; coste = `fldCantidad × precio_costo`; margen = venta sin IVA − coste. El coste es el actual: en periodos antiguos es aproximado. |
| ¿Qué cambió en el catálogo desde ayer? | `GET /api/skus?actualizado_desde=<ISO>&orden=actualizado&limit=500`, paginando. |

## 7. Trampas frecuentes

1. **No sumes importes de líneas para obtener totales de ticket**: usa
   `/api/ventas/cabeceras`. Las líneas no traen los totales de cabecera.
2. **`count` no es el total**: es el tamaño de la página. Pagina hasta
   `count < limit` antes de dar un recuento o una suma.
3. **El catálogo está por almacén**: un SKU no es una fila; para totales suma
   por almacén, y para contar SKUs distintos deduplica por `sku`.
4. **La talla en ventas se llama `fldTalla`**, en el resto `talla`.
5. **Los códigos son texto con ceros a la izquierda**: `00000207`, no `207`.
6. **`fldIdTicket` no es único** por sí solo; usa la clave natural completa.
7. **Fechas de cajas pendientes son texto**; las de ventas/compras son `date` y
   `actualizado_en` es datetime sin zona horaria.
8. **Solo existen los campos documentados**: si un dato no aparece aquí (coste,
   proveedor del SKU, empleado…), la API no lo ofrece. El margen no viene
   calculado: obténlo como se explica en la receta de márgenes.
9. **El stock puede ser negativo** (en `/api/skus` y `/api/stock`);
   `con_stock=true` solo deja stock > 0.
10. **Hay almacenes sin descripción** (`almacen_descripcion: null`): no
    inventes el nombre, muestra el `fldIdAlmacen`.

## 8. Ejemplo completo (Python)

```python
import requests

BASE = "https://bycos.data4tex.com"
tok = requests.post(f"{BASE}/auth/token",
                    data={"username": "USUARIO", "password": "CONTRASEÑA"}).json()
H = {"Authorization": f"Bearer {tok['access_token']}"}

def todo(path, **params):
    """Recorre todas las páginas de un listado."""
    params.setdefault("limit", 500)
    offset = 0
    while True:
        page = requests.get(f"{BASE}{path}", headers=H,
                            params={**params, "offset": offset}).json()
        yield from page["items"]
        if page["count"] < page["limit"]:
            break
        offset += page["limit"]

# Stock total del artículo 0100228002 en la tienda 00000207
stock = sum(r["stock_disponible"] or 0
            for r in todo("/api/skus", articulo="0100228002", almacen="00000207"))

# Facturación neta de julio 2025 en esa tienda
neto = sum(c["fldImporteNeto"] or 0
           for c in todo("/api/ventas/cabeceras", almacen="00000207",
                         fecha_desde="2025-07-01", fecha_hasta="2025-07-31"))
```
