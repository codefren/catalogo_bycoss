"""Seguridad compartida entre los routers: rate limiter y validación de API key.

Se extrae aquí para que `main.py` y los routers (sku, ventas) usen la MISMA
instancia de limiter y la misma dependencia de autenticación.
"""
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
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

# Cabecera donde el tercero manda su clave.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str = Security(api_key_header)) -> str:
    """Valida la clave en tiempo constante contra el conjunto configurado."""
    if key and any(secrets.compare_digest(key, k) for k in settings.api_key_set):
        return key
    raise HTTPException(status_code=401, detail="API key inválida o ausente")
