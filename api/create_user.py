"""Crea o actualiza un usuario de la API en la tabla `api_users`.

Guarda la contraseña como hash bcrypt (nunca en claro) y crea la tabla si no
existe, así que sirve también en una base ya desplegada (donde el initdb no se
vuelve a ejecutar).

Uso (dentro del contenedor del stack):
    docker compose exec api python create_user.py <usuario> <contraseña>
    docker compose exec api python create_user.py <usuario> <contraseña> --inactivo

La contraseña se pasa como argumento; si prefieres no dejarla en el historial
del shell, expórtala y pásala con comillas, o cámbiala luego.
"""
import asyncio
import sys

from sqlalchemy import text

from db import engine
from security import hash_password

_DDL = """
CREATE TABLE IF NOT EXISTS api_users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT        NOT NULL,
    activo        BOOLEAN     NOT NULL DEFAULT TRUE,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_UPSERT = """
INSERT INTO api_users (username, password_hash, activo)
VALUES (:u, :h, :a)
ON CONFLICT (username)
DO UPDATE SET password_hash = EXCLUDED.password_hash, activo = EXCLUDED.activo
"""


async def upsert_user(username: str, password: str, activo: bool) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(_DDL))
        await conn.execute(
            text(_UPSERT),
            {"u": username, "h": hash_password(password), "a": activo},
        )


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--inactivo"]
    activo = "--inactivo" not in sys.argv
    if len(args) != 2:
        print("Uso: python create_user.py <usuario> <contraseña> [--inactivo]")
        raise SystemExit(1)
    username, password = args
    asyncio.run(upsert_user(username, password, activo))
    print(f"Usuario '{username}' creado/actualizado (activo={activo}).")


if __name__ == "__main__":
    main()
