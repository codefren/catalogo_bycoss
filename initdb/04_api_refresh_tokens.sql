-- =============================================================================
--  Refresh tokens de la API (revocables).
--
--  El cliente recibe un refresh token opaco en /auth/token y lo renueva en
--  /auth/refresh. Aquí solo se guarda el HASH (SHA-256), nunca el valor.
--  La rotación revoca el token usado y crea uno nuevo; /auth/logout lo revoca.
--
--  Como el resto de initdb, esto SOLO se ejecuta al crear la base por primera
--  vez (volumen vacío). En una base ya existente, la app crea la tabla al
--  arrancar (lifespan).
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_refresh_tokens (
    token_hash TEXT PRIMARY KEY,          -- SHA-256 del refresh token
    username   TEXT        NOT NULL,
    expira_en  TIMESTAMPTZ NOT NULL,
    revocado   BOOLEAN     NOT NULL DEFAULT FALSE,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Para limpiar/consultar por usuario.
CREATE INDEX IF NOT EXISTS ix_refresh_username ON api_refresh_tokens (username);
