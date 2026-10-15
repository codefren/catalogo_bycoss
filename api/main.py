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
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from db import engine
from refresh_tokens import (
    REFRESH_DDL,
    resolve_refresh_token,
    revoke_refresh_token,
    store_refresh_token,
)
from routers import sku as sku_router
from routers import ventas as ventas_router
from schemas import RefreshIn, TokenOut
from security import (
    RATE_LIMIT_RESPONSE,
    create_access_token,
    create_refresh_token,
    limiter,
    require_jwt,
    verify_password,
)
from settings import settings
from users import USERS_DDL, get_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Al arrancar, asegura que existen las tablas de autenticación.

    Así funciona también sobre una base de prod ya creada (donde el initdb no se
    vuelve a ejecutar). Si fallara, no tumbamos la app: /health y /docs siguen.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text(USERS_DDL))
            await conn.execute(text(REFRESH_DDL))
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] no se pudieron asegurar las tablas de auth: {exc}")
    yield


async def _issue_tokens(username: str) -> TokenOut:
    """Emite el par access+refresh para un usuario y guarda el refresh en DB."""
    access, access_exp = create_access_token(subject=username)
    refresh, refresh_exp = create_refresh_token()
    expira_en = datetime.now(timezone.utc) + timedelta(seconds=refresh_exp)
    await store_refresh_token(username, refresh, expira_en)
    return TokenOut(
        access_token=access,
        token_type="bearer",
        expires_in=access_exp,
        refresh_token=refresh,
        refresh_expires_in=refresh_exp,
    )

# Agrupaciones que verás en Swagger, con descripción por grupo.
tags_metadata = [
    {"name": "Autenticación", "description": "Login (usuario + contraseña) que devuelve el token JWT."},
    {"name": "SKU — catálogo", "description": "Referencias del catálogo a nivel artículo-color-talla (tabla `sku`)."},
    {"name": "Ventas — líneas de ticket", "description": "Líneas de venta (tabla `ticket_maestro`); una fila por línea de ticket."},
    {"name": "Infra", "description": "Salud del servicio."},
]

app = FastAPI(
    title="Catálogo API",
    version="1.2.0",
    lifespan=lifespan,
    description=(
        "Consulta de **solo lectura** del catálogo (SKUs y ventas).\n\n"
        "**Autenticación (JWT con usuario):**\n"
        "1. `POST /auth/token` con **usuario** y **contraseña** (formulario), "
        "validados contra la tabla `api_users`.\n"
        "2. Recibes un `access_token` (JWT, **12 h**) y un `refresh_token` "
        "(opaco, **7 d**).\n"
        "3. Usa el access token en `/api/*` como `Authorization: Bearer <token>`.\n"
        "4. Cuando el access caduque, llama a `POST /auth/refresh` con el "
        "`refresh_token` para obtener uno nuevo (sin re-login). La rotación "
        "revoca el refresh usado y te da otro. `POST /auth/logout` lo revoca.\n\n"
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
    "contra la tabla `api_users`, devuelve un `access_token` (JWT, 12 h) y un "
    "`refresh_token` (7 d). Usa el access como `Authorization: Bearer <token>`.",
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
    return await _issue_tokens(form.username)


@app.post(
    "/auth/refresh",
    response_model=TokenOut,
    tags=["Autenticación"],
    summary="Renovar el access token",
    description="Envía el `refresh_token`. Devuelve un access token nuevo y, por "
    "rotación, un refresh token nuevo (el anterior queda revocado). Falla si el "
    "refresh está revocado, caducado o el usuario ya no está activo.",
    responses={401: {"description": "Refresh token inválido, revocado o expirado"}, **RATE_LIMIT_RESPONSE},
)
@limiter.limit(settings.rate_limit)
async def refresh(request: Request, body: RefreshIn):
    data = await resolve_refresh_token(body.refresh_token)
    if data is None:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")
    user = await get_user(data["username"])
    if user is None or not user["activo"]:
        raise HTTPException(status_code=401, detail="Usuario inactivo o inexistente")
    # Rotación: el refresh usado se revoca y se emite uno nuevo.
    await revoke_refresh_token(body.refresh_token)
    return await _issue_tokens(data["username"])


@app.post(
    "/auth/logout",
    tags=["Autenticación"],
    summary="Revocar un refresh token",
    description="Revoca el `refresh_token` indicado (cierre de sesión). El access "
    "token sigue siendo válido hasta que caduque (máx. 12 h).",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.limit(settings.rate_limit)
async def logout(request: Request, body: RefreshIn):
    await revoke_refresh_token(body.refresh_token)
    return {"detail": "Refresh token revocado"}


# ─────────────────────────────────────────────────────────────────────────────
#  Routers de las tablas reales del catálogo
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(sku_router.router)
app.include_router(ventas_router.router)
