"""API de solo lectura para exponer el catálogo a terceros.

Seguridad:
  · Autenticación JWT con usuario: POST /auth/token recibe usuario + contraseña
    (validados contra la tabla `api_users`, hash bcrypt) y devuelve un JWT que
    caduca a las 12 h. Los endpoints de datos exigen ese token en
    `Authorization: Bearer <token>`.
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
from fastapi.security import OAuth2PasswordRequestForm
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from db import engine
from routers import sku as sku_router
from routers import ventas as ventas_router
from schemas import TokenOut
from security import (
    RATE_LIMIT_RESPONSE,
    create_access_token,
    limiter,
    require_jwt,
    verify_password,
)
from settings import settings
from users import get_user

# Agrupaciones que verás en Swagger, con descripción por grupo.
tags_metadata = [
    {"name": "Autenticación", "description": "Login (usuario + contraseña) que devuelve el token JWT."},
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
        "**Autenticación (JWT con usuario):**\n"
        "1. Llama a `POST /auth/token` con tu **usuario** y **contraseña** "
        "(formulario). Se validan contra la tabla `api_users`.\n"
        "2. Recibes un `access_token` (JWT) que **caduca a las 12 h**.\n"
        "3. Usa ese token en los endpoints `/api/*` como "
        "`Authorization: Bearer <token>`.\n\n"
        "En Swagger: pulsa **Authorize** (arriba), introduce usuario y "
        "contraseña y listo.\n\n"
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
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


# ── Health (sin auth): lo usa el healthcheck del contenedor ──────────────────
@app.get("/health", tags=["Infra"], summary="Estado del servicio")
async def health():
    return {"status": "ok"}


# ── Autenticación: login con usuario + contraseña → JWT ──────────────────────
@app.post(
    "/auth/token",
    response_model=TokenOut,
    tags=["Autenticación"],
    summary="Login (usuario + contraseña)",
    description="Envía `username` y `password` (formulario). Si son válidos "
    "contra la tabla `api_users`, devuelve un JWT que caduca a las 12 h. Úsalo "
    "luego como `Authorization: Bearer <token>` en los endpoints `/api/*`.",
    responses={401: {"description": "Usuario o contraseña incorrectos"}, **RATE_LIMIT_RESPONSE},
)
@limiter.limit(settings.rate_limit)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    user = await get_user(form.username)
    if (
        user is None
        or not user["activo"]
        or not verify_password(form.password, user["password_hash"])
    ):
        raise HTTPException(
            status_code=401,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(subject=form.username)
    return TokenOut(access_token=token, token_type="bearer", expires_in=expires_in)


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
    _: dict = Depends(require_jwt),
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
    _: dict = Depends(require_jwt),
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
    _: dict = Depends(require_jwt),
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
