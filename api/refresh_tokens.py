"""Almacén de refresh tokens en Postgres (revocables).

El cliente recibe un refresh token opaco (aleatorio). En la base solo se guarda
su hash SHA-256, nunca el valor en claro. En /auth/refresh se valida, se revoca
el usado (rotación) y se emite uno nuevo; /auth/logout lo revoca.

Tabla:
    api_refresh_tokens(token_hash PK, username, expira_en, revocado, creado_en)
"""
import hashlib
from datetime import datetime, timezone

from sqlalchemy import text

from db import engine

# DDL; se aplica en el arranque (lifespan) y existe también en initdb/.
REFRESH_DDL = """
CREATE TABLE IF NOT EXISTS api_refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    username   TEXT        NOT NULL,
    expira_en  TIMESTAMPTZ NOT NULL,
    revocado   BOOLEAN     NOT NULL DEFAULT FALSE,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _hash(token: str) -> str:
    """SHA-256 del token. Sirve porque el token es aleatorio de alta entropía."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def store_refresh_token(username: str, token: str, expira_en: datetime) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO api_refresh_tokens (token_hash, username, expira_en) "
                "VALUES (:h, :u, :e)"
            ),
            {"h": _hash(token), "u": username, "e": expira_en},
        )


async def resolve_refresh_token(token: str) -> dict | None:
    """Devuelve {username} si el token existe, NO está revocado y NO ha caducado.

    En cualquier otro caso devuelve None.
    """
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT username, expira_en, revocado "
                    "FROM api_refresh_tokens WHERE token_hash = :h"
                ),
                {"h": _hash(token)},
            )
        ).mappings().first()
    if row is None or row["revocado"]:
        return None
    if row["expira_en"] <= datetime.now(timezone.utc):
        return None
    return {"username": row["username"]}


async def revoke_refresh_token(token: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE api_refresh_tokens SET revocado = TRUE WHERE token_hash = :h"),
            {"h": _hash(token)},
        )
