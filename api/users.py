"""Acceso a la tabla `api_users` (usuarios que se autentican contra la API).

Tabla:
    api_users(username TEXT PK, password_hash TEXT, activo BOOL, creado_en TIMESTAMPTZ)

El hash es bcrypt (ver security.hash_password). Para crear usuarios usa el
script api/create_user.py.
"""
from sqlalchemy import text

from db import engine


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
