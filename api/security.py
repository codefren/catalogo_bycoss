"""Seguridad compartida entre los routers: rate limiter y autenticación.

Modelo de autenticación (JWT con usuario):
  1. El cliente llama a POST /auth/token con `username` + `password`
     (formulario OAuth2 password). Se valida contra la tabla `api_users`
     (hash bcrypt).
  2. Recibe un JWT (HS256) con `sub = username`, que caduca a las
     `access_token_expire_hours` (12 h).
  3. Los endpoints de datos exigen ese JWT en `Authorization: Bearer <token>`
     (require_jwt).
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from settings import settings

# Un único limiter para toda la app. El estado se engancha en main.py
# (app.state.limiter = limiter).
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

# Respuesta 429 documentada en Swagger para los endpoints con rate limit.
# Se añade a `responses=` de cada endpoint de datos.
RATE_LIMIT_RESPONSE = {
    429: {"description": f"Límite de peticiones superado ({settings.rate_limit} por IP)."}
}

# Esquema OAuth2 password: en Swagger muestra el diálogo "Authorize" con
# usuario/contraseña y llama solo a /auth/token para obtener el Bearer.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


# ── Contraseñas (bcrypt) ─────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash bcrypt de una contraseña (para create_user.py)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Comprueba una contraseña contra su hash bcrypt (no lanza)."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────
def create_access_token(subject: str) -> tuple[str, int]:
    """Crea un JWT firmado (HS256) con sub=subject que caduca en 12 h.

    Devuelve (token, segundos_hasta_caducidad).
    """
    expires_in = settings.access_token_expire_hours * 3600
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


async def require_jwt(token: str | None = Security(oauth2_scheme)) -> dict:
    """Valida el JWT (Authorization: Bearer). 401 si falta/expira/inválido.

    Devuelve el payload decodificado (incluye `sub` = usuario).
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Falta el token Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
