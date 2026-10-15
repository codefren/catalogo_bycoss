"""API de solo lectura para exponer el catálogo a terceros.

Seguridad:
  · Autenticación por clave de API en la cabecera `X-API-Key` (comparación en
    tiempo constante). Todos los endpoints de datos la exigen.
  · CORS restringido a los orígenes configurados (nunca "*").
  · Rate limiting por IP (slowapi).
  · Consultas parametrizadas (bind params): sin inyección SQL.
  · Solo GET: los terceros consultan; la ACTUALIZACIÓN del catálogo la hace
    Databricks por JDBC directo a Postgres, no pasa por aquí.
"""
import secrets

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from db import engine
from settings import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(
    title="Catálogo API",
    version="1.0.0",
    description="Consulta de solo lectura del catálogo.",
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _ratelimit_handler(request: Request, exc: RateLimitExceeded):
    raise HTTPException(status_code=429, detail="Demasiadas peticiones")


if settings.cors_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_methods=["GET"],
        allow_headers=["X-API-Key"],
    )

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str = Security(api_key_header)) -> str:
    """Valida la clave en tiempo constante contra el conjunto configurado."""
    if key and any(secrets.compare_digest(key, k) for k in settings.api_key_set):
        return key
    raise HTTPException(status_code=401, detail="API key inválida o ausente")


# ── Health (sin auth): lo usa el healthcheck del contenedor ──────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Listado de artículos ─────────────────────────────────────────────────────
@app.get("/api/articulos")
@limiter.limit(settings.rate_limit)
async def list_articulos(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    categoria: str | None = Query(None, max_length=100),
    _: str = Depends(require_api_key),
):
    sql = "SELECT id, codigo, descripcion, categoria, actualizado FROM articulos"
    params: dict = {}
    if categoria:
        sql += " WHERE categoria = :categoria"
        params["categoria"] = categoria
    sql += " ORDER BY id LIMIT :limit OFFSET :offset"
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    return {"items": [dict(r) for r in rows], "limit": limit, "offset": offset}


# ── Un artículo por id ───────────────────────────────────────────────────────
@app.get("/api/articulos/{articulo_id}")
@limiter.limit(settings.rate_limit)
async def get_articulo(
    request: Request,
    articulo_id: int,
    _: str = Depends(require_api_key),
):
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT id, codigo, descripcion, categoria, actualizado "
                    "FROM articulos WHERE id = :id"
                ),
                {"id": articulo_id},
            )
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return dict(row)


# ── Existencias de un artículo ───────────────────────────────────────────────
@app.get("/api/articulos/{articulo_id}/existencias")
@limiter.limit(settings.rate_limit)
async def get_existencias(
    request: Request,
    articulo_id: int,
    _: str = Depends(require_api_key),
):
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT articulo_id, almacen, cantidad, actualizado "
                    "FROM existencias WHERE articulo_id = :id ORDER BY almacen"
                ),
                {"id": articulo_id},
            )
        ).mappings().all()
    return {"items": [dict(r) for r in rows]}
