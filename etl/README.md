# ETL catálogo — SQL Server → PostgreSQL (sin Databricks)

Reemplazo en Docker del pipeline de Databricks. Por cada tabla del catálogo:
extrae las fuentes de **SQL Server (Arsys)** al esquema `raw`, aplica la
transformación en **SQL de Postgres** y carga la tabla final `public.*` que
sirve la API. Sin Spark, sin Delta, sin tope diario.

Porta los jobs `bycos_pg_exports/*.py` de Databricks, uno por tabla.

## Estado

- [x] `sku` → `public.sku` (overwrite espejo) — **fase 1, en construcción/validación**
- [ ] `stock` → `public.stock`
- [ ] `stock_talla` → `public.stock_talla`
- [ ] `compras_maestro` → `public.compras_maestro`
- [ ] `ticket_maestro` → `public.ticket_maestro` (incremental)
- [ ] `cajas_pendientes` → `public.cajas_pendientes`

## Cómo funciona

```
SQL Server (dbo.tbd*) --extract--> Postgres raw.* --transform(SQL)--> public.*
```

- **extract.py**: copia una consulta de SQL Server a `raw.<tabla>` (columnas en
  minúscula, tipo text; carga por lotes con COPY). Robusto a tipos.
- **tables/<tabla>.py**: define las fuentes, el DDL destino y el `SELECT` de
  transformación (el *unpivot* de las 15 posiciones de talla se genera en Python,
  igual que en Databricks). Castea a numérico lo que hace falta.
- **etl.py**: orquesta extract → transform → load. La carga es transaccional
  (`TRUNCATE` + `INSERT`), así la API nunca ve datos a medias.

## Instalación

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # y rellena las credenciales
```

## Uso

**Siempre prueba primero con `--dry-run`** (calcula y muestra una muestra, NO
escribe en Postgres):

```bash
python etl.py sku --dry-run
```

Cuando la cuente y la muestra tengan buena pinta, carga de verdad:

```bash
python etl.py sku
```

## Docker (servicio en el compose del catálogo)

El ETL está en el `docker-compose.yml` del catálogo como servicio **`etl`**, tras
el *profile* `etl` para que **NO arranque** con el resto del stack (así no
escribe en prod por sorpresa).

En el `.env` de la **raíz** del proyecto (el que lee docker-compose) añade las
credenciales del SQL Server de origen (Postgres ya está):

```
SQLSERVER_HOST=82.223.100.253
SQLSERVER_PORT=4313
SQLSERVER_DB=S4T_BYCOS
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=...
```

(El Postgres destino lo toma del compose: servicio `postgres`, con `POSTGRES_*`.)

**Una pasada de prueba (segura, no escribe):**
```bash
docker compose run --rm etl sku --dry-run
```

**Una carga real, una vez:**
```bash
docker compose run --rm etl sku
```

**Programado (bucle cada hora, en segundo plano):**
```bash
docker compose --profile etl up -d --build etl
docker compose logs -f etl
```

Cambia el intervalo o las tablas editando el `command` del servicio `etl` en
`docker-compose.yml` (por defecto `--loop --interval 3600 sku`).

## Añadir una tabla

1. Crea `tables/<tabla>.py` con `SOURCES`, `TARGET_DDL`, `TARGET_COLUMNS`,
   `KEYS` y `build_select()` (mira `tables/sku.py` como plantilla).
2. Regístrala en `TABLES` de `etl.py`.
3. `python etl.py <tabla> --dry-run`.
