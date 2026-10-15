-- =============================================================================
--  Usuarios de la API (login con usuario + contraseña → JWT).
--
--  La contraseña se guarda como hash bcrypt (nunca en claro). Para crear o
--  actualizar usuarios usa el script, que también crea esta tabla si falta:
--     docker compose exec api python create_user.py <usuario> <contraseña>
--
--  Como el resto de initdb, esto SOLO se ejecuta al crear la base por primera
--  vez (volumen vacío). En una base ya existente, la tabla la crea el script.
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT        NOT NULL,     -- bcrypt
    activo        BOOLEAN     NOT NULL DEFAULT TRUE,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
