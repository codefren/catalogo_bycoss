"""Acceso a la tabla `api_users` (usuarios que se autentican contra la API).

Tabla:
    api_users(username TEXT PK, password_hash TEXT, activo BOOL, creado_en TIMESTAMPTZ)

El hash es bcrypt (ver security.hash_password). Para crear usuarios usa el
script api/create_user.py.
"""
from sqlalchemy import text

from db import engine

# DDL de la tabla de usuarios. Se usa en el arranque (lifespan) y en
# create_user.py para que funcione también sobre una base ya existente.
USERS_DDL = """
CREATE TABLE IF NOT EXISTS api_users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT        NOT NULL,
    activo        BOOLEAN     NOT NULL DEFAULT TRUE,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def get_user(username: str) -> dict | None:
    """Devuelve {username, password_hash, activo} o None si no existe."""
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT username, password_hash, activo "
                    "FROM api_users WHERE username = :u"
                ),
                {"u": username},
            )
        ).mappings().first()
    return dict(row) if row else None
