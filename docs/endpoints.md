# Endpoints de la Catálogo API

API de **solo lectura**. Todos los `/api/*` requieren un **access token** JWT en
la cabecera `Authorization: Bearer <token>` (ver [autenticacion.md](autenticacion.md)
para obtenerlo). Las respuestas son JSON.

- Base URL: `https://bycos.data4tex.com`
- Swagger: `/docs` · ReDoc: `/redoc` · OpenAPI: `/openapi.json`
- Contexto para asistentes (Claude/LLM): `/contexto-api.md` (fuente:
  `api/contexto_api.md`; actualízalo cuando cambie un endpoint)

## Paginación

Los listados (`/api/skus`, `/api/stock`, `/api/ventas`, `/api/ventas/cabeceras`,
`/api/compras`, `/api/cajas-pendientes`) paginan con **`limit` / `offset`** y
devuelven un **sobre paginado**:

```json
{ "items": [ ... ], "count": 2, "limit": 50, "offset": 0 }
```

| Campo | Significado |
|---|---|
| `items` | Filas de esta página. |
| `count` | Nº de filas devueltas **en esta página** (no el total de la consulta: la API no calcula totales). |
| `limit` | Tamaño de página solicitado: 1–500, por defecto 50. Fuera de rango → `422`. |
| `offset` | Filas que se saltan antes de empezar la página: ≥ 0, por defecto 0. |

Por dentro es `ORDER BY ... LIMIT :limit OFFSET :offset`: la página *n*
(empezando en 0) se pide con `offset = n × limit`.

**Cómo saber que no hay más páginas:** cuando `count < limit`. Si `count == limit`
puede haber más (o ninguna: la siguiente vendrá con `items: []`).

**Leerlo todo:**

```bash
offset=0
while :; do
  page=$(curl -s "$BASE/api/compras?fecha_desde=2025-06-01&limit=500&offset=$offset" \
    -H "Authorization: Bearer $ACCESS")
  echo "$page" | jq -c '.items[]'
  [ "$(echo "$page" | jq .count)" -lt 500 ] && break
  offset=$((offset + 500))
done
```

**Orden de cada listado** (es lo que determina qué filas caen en cada página).
Todos los listados tienen un **orden total**: el `ORDER BY` termina en una clave
única, así que dos filas nunca empatan y repetir la misma consulta devuelve
siempre las mismas filas en cada página.

| Endpoint | Orden |
|---|---|
| `/api/skus` | El de `orden`/`direccion` y, para desempatar, `sku`, `fldIdAlmacen`. |
| `/api/stock` | El de `orden`/`direccion` y, para desempatar, `fldIdAlmacen`, `fldIdArticulo`, `fldIdColor`, `talla`. |
| `/api/ventas` | `fecha` desc, `fldIdTicket`, `fldLinea`, `fldIdEmpresa`, `fldIdAlmacen`, `fldIdCaja`. |
| `/api/ventas/cabeceras` | `fecha` desc, `fldIdTicket`, `fldIdEmpresa`, `fldIdAlmacen`, `fldIdCaja`. |
| `/api/compras` | `fecha` desc, `fldIdProveedor`, `fldIdArticulo`, `fldIdColor`, `talla_pos`, `fldIdAlmacen`. |
| `/api/cajas-pendientes` | `FechaSalida` desc, `CodigoCaja`, `Articulo`, `Color`, `Talla`. |

En stock, ventas, compras y cajas el último desempate es la posición física de la fila
(`ctid` de Postgres), porque esas tablas no tienen una clave única: así hasta las
filas duplicadas tienen un orden fijo.

Ten en cuenta:

- **Los datos pueden cambiar entre páginas:** si se recargan mientras paginas,
  puede haber filas repetidas o saltadas. Para extracciones completas, acota por
  fechas (o, en SKU, por `actualizado_desde`) y no pagines durante una carga.
- **Rendimiento:** `offset` alto obliga a la base a recorrer y descartar todas
  las filas anteriores. Usa `limit=500` y acota con filtros en lugar de paginar
  tablas enteras.
- Los endpoints de detalle (`/api/skus/{sku}`, `/api/stock/almacenes`,
  `/api/ventas/ticket/...`, `/api/cajas-pendientes/caja/{codigo_caja}`) devuelven todas las filas de una vez, no
  aceptan `limit`/`offset` y en su sobre `limit == count`, `offset == 0`.

**Uso recomendado:** hasta **1080 peticiones por minuto**.

---

## SKU — catálogo (`sku`)

Grano: **una fila por SKU (artículo-color-talla) y almacén**. Un mismo SKU sale
una vez por cada almacén (`fldIdAlmacen`) que lo tenga.

Campos devueltos: `sku`, `fldIdAlmacen`, `fldIdArticulo`, `articulo_descripcion`,
`fldTemporada`, `fldIdFamilia`, `fldReferencia`, `codigo_barras`, `fldColeccion`,
`fldIdMarca`, `fldIdColor`, `color_descripcion`, `fldIdGrupoTallas`,
`grupotalla_descripcion`, `talla`, `pvp`, `stock_disponible`, `actualizado_en`.
(No se exponen coste, proveedor, parámetros de reposición ni totales de
movimiento.)

### `GET /api/skus`
Lista paginada. Todos los filtros son opcionales y se combinan con **AND**. Los
marcados como *repetible* aceptan varios valores repitiendo el parámetro
(`?almacen=A&almacen=B`), que se combinan con **OR** (máx. 50 valores).

| Filtro | Columna | Descripción |
|--------|---------|-------------|
| `q` | `articulo_descripcion` | Texto parcial en la descripción (sin distinguir mayúsculas). |
| `sku_prefijo` | `sku` | SKUs que empiezan por este texto. |
| `almacen` | `fldIdAlmacen` | Igualdad exacta, *repetible*. |
| `articulo` | `fldIdArticulo` | Todas las **permutas** (color/talla) de un artículo, *repetible*. |
| `temporada` | `fldTemporada` | Igualdad exacta, *repetible*. |
| `familia` | `fldIdFamilia` | Igualdad exacta, *repetible*. |
| `marca` | `fldIdMarca` | Igualdad exacta, *repetible*. |
| `coleccion` | `fldColeccion` | Igualdad exacta, *repetible*. |
| `color` | `fldIdColor` | Igualdad exacta, *repetible*. |
| `grupo_tallas` | `fldIdGrupoTallas` | Igualdad exacta, *repetible*. |
| `talla` | `talla` | Igualdad exacta, *repetible*. |
| `codigo_barras` | `codigo_barras` | EAN exacto, *repetible*. |
| `referencia` | `fldReferencia` | Igualdad exacta, *repetible*. |
| `pvp_min`, `pvp_max` | `pvp` | Rango de PVP (inclusive). |
| `stock_min`, `stock_max` | `stock_disponible` | Rango de stock (inclusive). |
| `con_stock` | `stock_disponible` | `true` → solo con stock > 0. |
| `actualizado_desde` | `actualizado_en` | Fecha/hora ISO 8601; filas actualizadas desde entonces (sync incremental). |
| `orden` | — | `sku` (defecto), `articulo`, `pvp`, `stock`, `actualizado`. |
| `direccion` | — | `asc` (defecto) o `desc`. |
| `limit`, `offset` | — | Paginación. |

Los nulos van siempre al final y se desempata por `sku` + `fldIdAlmacen`, así la
paginación es estable.

```bash
# Todas las permutas del artículo 0100228002
curl -s "$BASE/api/skus?articulo=0100228002&limit=500" -H "Authorization: Bearer $ACCESS"

# Con stock en dos tiendas, temporada V25, PVP entre 20 y 50, más caros primero
curl -s "$BASE/api/skus?almacen=00000207&almacen=00000208&temporada=V25&pvp_min=20&pvp_max=50&con_stock=true&orden=pvp&direccion=desc" \
  -H "Authorization: Bearer $ACCESS"

# Cambios desde una fecha (sincronización incremental)
curl -s "$BASE/api/skus?actualizado_desde=2025-10-14T00:00:00&orden=actualizado&limit=500" \
  -H "Authorization: Bearer $ACCESS"
```

### `GET /api/skus/{sku}`
Las filas de un SKU, **una por almacén**, ordenadas por almacén (mismo sobre
paginado que el listado). `almacen` (*repetible*) limita a esos almacenes.
`404` si no hay ninguna fila.

```bash
curl -s "$BASE/api/skus/0100228002-000005-U" -H "Authorization: Bearer $ACCESS"
curl -s "$BASE/api/skus/0100228002-000005-U?almacen=00000207" -H "Authorization: Bearer $ACCESS"
```

---

## Stock por almacén (`stock`)

Grano: **una fila por artículo-color-talla y almacén**. A diferencia de `sku`,
incluye la **descripción del almacén** (`almacen_descripcion`).

Campos devueltos: `fldIdAlmacen`, `almacen_descripcion`, `fldIdArticulo`,
`fldIdColor`, `talla`, `stock_disponible`, `actualizado_en`. (No se exponen los
totales de movimiento: entradas, salidas, servicio, tránsito.)

`stock_disponible` es el stock **de ese almacén** y **puede ser negativo**. Para
el total de un artículo en varias tiendas, suma `stock_disponible` de sus filas.

### `GET /api/stock`
Lista paginada. Todos los filtros son opcionales y se combinan con **AND**; los
*repetibles* combinan sus valores con **OR** (máx. 50 valores).

| Filtro | Columna | Descripción |
|--------|---------|-------------|
| `almacen` | `fldIdAlmacen` | Igualdad exacta, *repetible*. |
| `almacen_nombre` | `almacen_descripcion` | Texto parcial en la descripción del almacén (sin distinguir mayúsculas). |
| `articulo` | `fldIdArticulo` | Igualdad exacta, *repetible*. |
| `color` | `fldIdColor` | Igualdad exacta, *repetible*. |
| `talla` | `talla` | Igualdad exacta, *repetible*. |
| `stock_min`, `stock_max` | `stock_disponible` | Rango de stock (inclusive); `stock_min > stock_max` → `422`. |
| `con_stock` | `stock_disponible` | `true` → solo con stock > 0 (excluye los negativos). |
| `actualizado_desde` | `actualizado_en` | Fecha/hora ISO 8601; filas actualizadas desde entonces (sync incremental). |
| `orden` | — | `almacen` (defecto), `articulo`, `stock`, `actualizado`. |
| `direccion` | — | `asc` (defecto) o `desc`. |
| `limit`, `offset` | — | Paginación. |

```bash
# Stock del artículo 0100228002 en una tienda, con su nombre
curl -s "$BASE/api/stock?articulo=0100228002&almacen=00000207" -H "Authorization: Bearer $ACCESS"

# Stock total del artículo en todas las tiendas
curl -s "$BASE/api/stock?articulo=0100228002&limit=500" -H "Authorization: Bearer $ACCESS" \
  | jq '[.items[].stock_disponible // 0] | add'

# Lo que tiene stock en las tiendas cuyo nombre contiene "centro", más stock primero
curl -s "$BASE/api/stock?almacen_nombre=centro&con_stock=true&orden=stock&direccion=desc" \
  -H "Authorization: Bearer $ACCESS"
```

### `GET /api/stock/almacenes`
Todos los almacenes con su descripción (`fldIdAlmacen`, `almacen_descripcion`),
ordenados por código. **No pagina**: devuelve la lista completa en el sobre
habitual, con `limit == count` y `offset == 0`. Sirve para traducir el
`fldIdAlmacen` de cualquier otro endpoint a su nombre.

```bash
curl -s "$BASE/api/stock/almacenes" -H "Authorization: Bearer $ACCESS"
```

---

## Ventas — líneas de ticket (`ticket_maestro`)

### `GET /api/ventas`
Lista paginada de líneas de ticket (una fila por línea). Ordena por fecha
descendente.

| Filtro | Columna | Descripción |
|--------|---------|-------------|
| `fecha_desde` | `fecha` | Fecha **mínima** (inclusive), `YYYY-MM-DD`. |
| `fecha_hasta` | `fecha` | Fecha **máxima** (inclusive), `YYYY-MM-DD`. |
| `almacen` | `fldIdAlmacen` | Igualdad exacta. |
| `ticket` | `fldIdTicket` | Igualdad exacta. |
| `sku` | `sku` | Igualdad exacta (SKU vendido). |
| `cliente` | `fldIdCliente` | Igualdad exacta. |
| `limit`, `offset` | — | Paginación. |

**Rango de fechas:** `fecha_desde` y `fecha_hasta` son independientes; puedes
usar una, otra o ambas. Ambas incluyen el día indicado.

```bash
# Ventas de julio de 2025 (rango cerrado)
curl -s "$BASE/api/ventas?fecha_desde=2025-07-01&fecha_hasta=2025-07-31&limit=500" \
  -H "Authorization: Bearer $ACCESS"

# Ventas desde una fecha en adelante
curl -s "$BASE/api/ventas?fecha_desde=2025-01-01" -H "Authorization: Bearer $ACCESS"

# Rango de fechas de un almacén concreto
curl -s "$BASE/api/ventas?fecha_desde=2025-06-01&fecha_hasta=2025-06-30&almacen=00000207" \
  -H "Authorization: Bearer $ACCESS"

# Rango de fechas de un SKU concreto
curl -s "$BASE/api/ventas?fecha_desde=2025-01-01&fecha_hasta=2025-12-31&sku=0100228002-000005-U" \
  -H "Authorization: Bearer $ACCESS"
```

> Nota: para rangos grandes usa `limit` (máx. 500) y pagina con `offset`, o
> acota con más filtros.

### `GET /api/ventas/ticket/{empresa}/{almacen}/{caja}/{ticket}`
Todas las líneas de un ticket por su clave natural (empresa, almacén, caja,
ticket), ordenadas por línea. `404` si no hay líneas.

```bash
curl -s "$BASE/api/ventas/ticket/0001/00000207/000001/2072056051" \
  -H "Authorization: Bearer $ACCESS"
```

### `GET /api/ventas/cabeceras`
Lista paginada de **cabeceras** de ticket. Como `ticket_maestro` tiene una fila
por línea y los totales se repiten idénticos en todas las líneas del mismo
ticket, este endpoint los **agrega por la clave natural** y devuelve **una sola
fila por ticket** con sus totales (sin duplicarlos por línea). Ordena por fecha
descendente.

No incluye operario/cajera ni códigos internos (mismo criterio de las líneas).
Los totales que expone son: `fldPrendas`, `fldImporteBruto`, `fldImporteDto`,
`fldImporteNeto`, `fldCobradoTicket`, `fldPteTicket`, `dto_cabecera`, `fldVales`,
`fldApartados`, `fldArreglos`, `fldPromociones`, `fldChequeRegalo`, `fldCupones`
y `fldEspecial`, junto a la clave natural, `fecha`, `fldHora`, `fldIdCliente`,
`fldIdMoneda` y `fldCambio`.

| Filtro | Columna | Descripción |
|--------|---------|-------------|
| `fecha_desde` | `fecha` | Fecha **mínima** (inclusive), `YYYY-MM-DD`. |
| `fecha_hasta` | `fecha` | Fecha **máxima** (inclusive), `YYYY-MM-DD`. |
| `almacen` | `fldIdAlmacen` | Igualdad exacta. |
| `cliente` | `fldIdCliente` | Igualdad exacta. |
| `ticket` | `fldIdTicket` | Igualdad exacta. |
| `limit`, `offset` | — | Paginación. |

```bash
# Cabeceras (totales) de julio de 2025
curl -s "$BASE/api/ventas/cabeceras?fecha_desde=2025-07-01&fecha_hasta=2025-07-31&limit=500" \
  -H "Authorization: Bearer $ACCESS"
```

### `GET /api/ventas/cabecera/{empresa}/{almacen}/{caja}/{ticket}`
La cabecera (totales) de **un** ticket por su clave natural, en una sola fila
(objeto, no sobre paginado). `404` si el ticket no existe.

```bash
curl -s "$BASE/api/ventas/cabecera/0001/00000207/000001/2072056051" \
  -H "Authorization: Bearer $ACCESS"
```

---

## Compras — líneas de compra (`compras_maestro`)

### `GET /api/compras`
Lista paginada de líneas de compra a proveedor (una fila por artículo-color-talla
comprado). Ordena por fecha descendente.

| Filtro | Columna | Descripción |
|--------|---------|-------------|
| `fecha_desde` | `fecha` | Fecha **mínima** (inclusive), `YYYY-MM-DD`. |
| `fecha_hasta` | `fecha` | Fecha **máxima** (inclusive), `YYYY-MM-DD`. |
| `almacen` | `fldIdAlmacen` | Igualdad exacta. |
| `proveedor` | `fldIdProveedor` | Igualdad exacta. |
| `articulo` | `fldIdArticulo` | Igualdad exacta. |
| `color` | `fldIdColor` | Igualdad exacta. |
| `talla` | `talla` | Igualdad exacta. |
| `temporada` | `fldTemporada` | Igualdad exacta. |
| `familia` | `fldIdFamilia` | Igualdad exacta. |
| `limit`, `offset` | — | Paginación. |

**Rango de fechas:** `fecha_desde` y `fecha_hasta` son independientes; puedes
usar una, otra o ambas. Ambas incluyen el día indicado.

```bash
# Compras de junio de 2025 (rango cerrado)
curl -s "$BASE/api/compras?fecha_desde=2025-06-01&fecha_hasta=2025-06-30&limit=500" \
  -H "Authorization: Bearer $ACCESS"

# Compras a un proveedor concreto
curl -s "$BASE/api/compras?proveedor=PROV012" -H "Authorization: Bearer $ACCESS"

# Compras de un artículo en una temporada
curl -s "$BASE/api/compras?articulo=0100228002&temporada=V25&limit=500" \
  -H "Authorization: Bearer $ACCESS"
```

> Nota: para rangos grandes usa `limit` (máx. 500) y pagina con `offset`, o
> acota con más filtros.

---

## Cajas pendientes (`cajas_pendientes`)

Cajas/envíos pendientes de llegada a tienda (una fila por artículo-color-talla
dentro de una caja). **Las claves del JSON van normalizadas a snake_case**
(p. ej. `codigo_caja`, `dispatch_note`) aunque en el origen las columnas sean
PascalCase; `total_prendas` y `cantidad` se devuelven como enteros y las fechas
como texto.

### `GET /api/cajas-pendientes`
Lista paginada. Ordena por fecha de salida descendente.

| Filtro | Columna origen | Descripción |
|--------|----------------|-------------|
| `tienda` | `Tienda` | Igualdad exacta. |
| `cliente` | `CodCliente` | Igualdad exacta. |
| `articulo` | `Articulo` | Igualdad exacta. |
| `ean` | `EAN` | Igualdad exacta (código de barras). |
| `caja` | `CodigoCaja` | Igualdad exacta. |
| `pedido` | `NoPedido` | Igualdad exacta. |
| `envio` | `NoEnvio` | Igualdad exacta. |
| `dispatch_note` | `DispathNote` | Igualdad exacta (albarán). |
| `limit`, `offset` | — | Paginación. |

> Nota: `fecha_salida` y `fecha_llegada` son **texto** en el origen, por eso no
> hay filtro por rango de fechas. Si el origen pasa a fecha real (o se confirma
> el formato), se añade.

```bash
# Cajas pendientes de una tienda
curl -s "$BASE/api/cajas-pendientes?tienda=00000207&limit=500" \
  -H "Authorization: Bearer $ACCESS"

# Buscar una prenda concreta por EAN
curl -s "$BASE/api/cajas-pendientes?ean=8412345678901" -H "Authorization: Bearer $ACCESS"
```

### `GET /api/cajas-pendientes/caja/{codigo_caja}`
Todas las líneas de una caja por su `CodigoCaja`, ordenadas por artículo, color y talla.
`404` si no hay líneas.

```bash
curl -s "$BASE/api/cajas-pendientes/caja/CJ0000998877" -H "Authorization: Bearer $ACCESS"
```

---

## Variables de los ejemplos

```bash
BASE=https://bycos.data4tex.com
# Obtén el access token (ver autenticacion.md):
ACCESS=$(curl -s -X POST "$BASE/auth/token" \
  --data-urlencode "username=bycos" --data-urlencode "password=TU_CONTRASEÑA" \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```
