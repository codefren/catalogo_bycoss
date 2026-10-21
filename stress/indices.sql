-- Índices recomendados para las consultas de la API.
--
-- Seguro de aplicar en producción: CONCURRENTLY no bloquea lecturas ni
-- escrituras (ni la API ni las cargas de Databricks). Cada sentencia va sola
-- (CONCURRENTLY no admite transacción): ejecútalo con
--   psql -U catalogo -d catalogo -f stress/indices.sql
-- IF NOT EXISTS lo hace re-ejecutable.
--
-- OJO: si Databricks recrea las tablas (mode("overwrite") sin truncate), los
-- índices se pierden y hay que volver a crearlos tras cada carga.

-- ── sku ──────────────────────────────────────────────────────────────────────
-- Orden por defecto del listado (ORDER BY sku, almacén) y detalle por SKU.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sku_sku_almacen   ON sku (sku, "fldIdAlmacen");
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sku_articulo      ON sku ("fldIdArticulo");
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sku_almacen       ON sku ("fldIdAlmacen");
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sku_codigo_barras ON sku (codigo_barras);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sku_actualizado   ON sku (actualizado_en);

-- ── ticket_maestro ───────────────────────────────────────────────────────────
-- Rango de fechas (listado de líneas y de cabeceras).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ticket_fecha ON ticket_maestro (fecha);
-- Clave natural del ticket (detalle de líneas y de cabecera, GROUP BY).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ticket_clave
    ON ticket_maestro ("fldIdEmpresa", "fldIdAlmacen", "fldIdCaja", "fldIdTicket");
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ticket_sku ON ticket_maestro (sku);

-- ── compras_maestro ──────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_compras_fecha ON compras_maestro (fecha);

-- ── cajas_pendientes ─────────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cajas_caja   ON cajas_pendientes ("CodigoCaja");
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cajas_tienda ON cajas_pendientes ("Tienda");

ANALYZE sku;
ANALYZE ticket_maestro;
ANALYZE compras_maestro;
ANALYZE cajas_pendientes;
