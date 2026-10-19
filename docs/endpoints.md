# Endpoints de la Catálogo API

API de **solo lectura**. Todos los `/api/*` requieren un **access token** JWT en
la cabecera `Authorization: Bearer <token>` (ver [autenticacion.md](autenticacion.md)
para obtenerlo). Las respuestas son JSON.

- Base URL: `https://bycos.data4tex.com`
- Swagger: `/docs` · ReDoc: `/redoc` · OpenAPI: `/openapi.json`

Los listados devuelven un **sobre paginado**:

```json
{ "items": [ ... ], "count": 2, "limit": 50, "offset": 0 }
```

- `limit`: tamaño de página (1–500, por defecto 50).
- `offset`: desplazamiento (paginación).
- `count`: nº de filas devueltas en esta página.

Todos los endpoints están sujetos al **rate limit** por IP (`60/minute` por
defecto); al superarlo devuelven `429`.

---

## SKU — catálogo (`sku`)

### `GET /api/skus`
Lista paginada de SKUs (una fila por artículo-color-talla).

| Filtro | Columna | Descripción |
|--------|---------|-------------|
| `articulo` | `fldIdArticulo` | Todas las **permutas** (color/talla) de un artículo. |
| `q` | `articulo_descripcion` | Texto parcial en la descripción (sin distinguir mayúsculas). |
| `temporada` | `fldTemporada` | Igualdad exacta. |
| `familia` | `fldIdFamilia` | Igualdad exacta. |
| `proveedor` | `fldIdProveedor` | Igualdad exacta. |
| `marca` | `fldIdMarca` | Igualdad exacta. |
| `color` | `fldIdColor` | Igualdad exacta. |
| `talla` | `talla` | Igualdad exacta. |
| `con_stock` | `stock_disponible` | `true` → solo con stock > 0. |
| `limit`, `offset` | — | Paginación. |

Ordena por código de SKU.

```bash
# Todas las permutas del artículo 0100228002
curl -s "$BASE/api/skus?articulo=0100228002&limit=500" -H "Authorization: Bearer $ACCESS"
```

### `GET /api/skus/{sku}`
Una referencia por su código de SKU. `404` si no existe.

```bash
curl -s "$BASE/api/skus/0100228002-000005-U" -H "Authorization: Bearer $ACCESS"
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
Todas las líneas de una caja por su `CodigoCaja`, ordenadas por artículo y talla.
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
