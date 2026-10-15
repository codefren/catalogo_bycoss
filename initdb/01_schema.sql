-- =============================================================================
--  Esquema del catálogo — 2 tablas.
--
--  PLANTILLA: adapta nombres, columnas y tipos a tu catálogo real. Este script
--  se ejecuta SOLO la primera vez que se crea la base (volumen vacío). Si ya
--  existe la base y quieres cambiar el esquema, aplícalo a mano con psql.
--
--  Lo importante para que las consultas/actualizaciones desde Databricks vayan
--  rápido a 250k filas: un ÍNDICE en la clave por la que buscas y actualizas.
-- =============================================================================

-- ── Tabla 1 ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articulos (
    id            BIGINT PRIMARY KEY,          -- clave de negocio (la de tu origen)
    codigo        TEXT        NOT NULL,
    descripcion   TEXT,
    categoria     TEXT,
    actualizado   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices de apoyo (ajusta a las columnas por las que filtras de verdad).
CREATE INDEX IF NOT EXISTS ix_articulos_codigo    ON articulos (codigo);
CREATE INDEX IF NOT EXISTS ix_articulos_categoria ON articulos (categoria);

-- ── Tabla 2 ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS existencias (
    articulo_id   BIGINT      NOT NULL REFERENCES articulos (id),
    almacen       TEXT        NOT NULL,
    cantidad      NUMERIC(14,3) NOT NULL DEFAULT 0,
    actualizado   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (articulo_id, almacen)   -- clave compuesta = índice automático
);
