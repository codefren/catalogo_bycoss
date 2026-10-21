"""Almacén de refresh tokens en Postgres (revocables).

El cliente recibe un refresh token opaco (aleatorio). En la base solo se guarda
su hash SHA-256, nunca el valor en claro. En /auth/refresh se valida, se revoca
el usado (rotación) y se emite uno nuevo; /auth/logout lo revoca.

Tabla:
    api_refresh_tokens(token_hash PK, username, expira_en, revocado, creado_en)
"""
import hashlib
from datetime import datetime

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


async def consume_refresh_token(token: str) -> str | None:
    """Canjea el token: si existe, NO está revocado y NO ha caducado, lo revoca y
    devuelve su username. En cualquier otro caso devuelve None.

    Comprobar y revocar van en el mismo UPDATE (atómico): si llegan dos
    peticiones a la vez con el mismo token, solo una obtiene la fila.
    """
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "UPDATE api_refresh_tokens SET revocado = TRUE "
                    "WHERE token_hash = :h AND NOT revocado AND expira_en > now() "
                    "RETURNING username"
                ),
                {"h": _hash(token)},
            )
        ).first()
    return row[0] if row else None


async def revoke_refresh_token(token: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE api_refresh_tokens SET revocado = TRUE WHERE token_hash = :h"),
            {"h": _hash(token)},
        )
