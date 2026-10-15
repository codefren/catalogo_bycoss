"""API de solo lectura para exponer el catálogo a terceros.

Seguridad:
  · Autenticación por clave de API en la cabecera `X-API-Key` (comparación en
    tiempo constante). Todos los endpoints de datos la exigen.
  · CORS restringido a los orígenes configurados (nunca "*").
  · Rate limiting por IP (slowapi).
  · Consultas parametrizadas (bind params): sin inyección SQL.
  · Solo GET: los terceros consultan; la ACTUALIZACIÓN del catálogo la hace
    Databricks por JDBC directo a Postgres, no pasa por aquí.

Documentación interactiva (Swagger UI): /docs   ·   ReDoc: /redoc
Esquema OpenAPI: /openapi.json
"""
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from db import engine
from routers import sku as sku_router
from routers import ventas as ventas_router
from security import limiter, require_api_key
from settings import settings

# Agrupaciones que verás en Swagger, con descripción por grupo.
tags_metadata = [
    {"name": "SKU — catálogo", "description": "Referencias del catálogo a nivel artículo-color-talla (tabla `sku`)."},
    {"name": "Ventas — líneas de ticket", "description": "Líneas de venta (tabla `ticket_maestro`); una fila por línea de ticket."},
    {"name": "Artículos (legacy)", "description": "Endpoints heredados del esqueleto inicial."},
    {"name": "Infra", "description": "Salud del servicio."},
]

app = FastAPI(
    title="Catálogo API",
    version="1.1.0",
    description=(
        "Consulta de **solo lectura** del catálogo (SKUs y ventas).\n\n"
        "**Autenticación:** envía tu clave en la cabecera `X-API-Key`. "
        "En Swagger, usa el botón **Authorize** (arriba a la derecha).\n\n"
        f"**Límite de peticiones (rate limiting):** máximo **{settings.rate_limit}** "
        "por IP, compartido por todos los endpoints `/api/*`. Al superarlo, la API "
        "responde `429 Too Many Requests`. El valor se configura con la variable "
        "de entorno `RATE_LIMIT` (formato de slowapi, p. ej. `60/minute`, "
        "`1/second`, `1000/hour`)."
    ),
    openapi_tags=tags_metadata,
    contact={"name": "Soporte catálogo", "email": "efrenoscar6@gmail.com"},
    license_info={"name": "Uso privado"},
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


# ── Health (sin auth): lo usa el healthcheck del contenedor ──────────────────
@app.get("/health", tags=["Infra"], summary="Estado del servicio")
async def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
#  Routers de las tablas reales del catálogo
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(sku_router.router)
app.include_router(ventas_router.router)


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints heredados del esqueleto inicial (tablas articulos/existencias).
#  OJO: su esquema asumido (id, codigo, descripcion…) puede no coincidir con las
#  columnas reales; se conservan para no romper integraciones previas.
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/articulos", tags=["Artículos (legacy)"])
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


@app.get("/api/articulos/{articulo_id}", tags=["Artículos (legacy)"])
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


@app.get("/api/articulos/{articulo_id}/existencias", tags=["Artículos (legacy)"])
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
