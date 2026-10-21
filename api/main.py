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
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from db import engine
from refresh_tokens import (
    REFRESH_DDL,
    consume_refresh_token,
    revoke_refresh_token,
    store_refresh_token,
)
from routers import cajas as cajas_router
from routers import compras as compras_router
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
    {"name": "SKU — catálogo", "description": "Referencias del catálogo a nivel artículo-color-talla y almacén (tabla `sku`); una fila por SKU y almacén."},
    {"name": "Ventas — líneas de ticket", "description": "Líneas de venta (tabla `ticket_maestro`); una fila por línea de ticket. Incluye también las **cabeceras** (`/api/ventas/cabeceras`), que agregan los totales de cada ticket en una sola fila."},
    {"name": "Compras — líneas de compra", "description": "Líneas de compra a proveedor (tabla `compras_maestro`); una fila por artículo-color-talla comprado."},
    {"name": "Cajas pendientes", "description": "Líneas de cajas/envíos pendientes de llegada a tienda (tabla `cajas_pendientes`); claves normalizadas a snake_case."},
    {"name": "Documentación", "description": "Contexto completo de la API en Markdown, listo para dárselo a un asistente (Claude u otro LLM)."},
    {"name": "Infra", "description": "Salud del servicio."},
]

# Contexto de la API para asistentes (LLM). Se lee una vez al arrancar.
CONTEXTO_PATH = Path(__file__).parent / "contexto_api.md"
CONTEXTO_MD = CONTEXTO_PATH.read_text(encoding="utf-8")

app = FastAPI(
    title="Catálogo API",
    version="1.3.0",
    lifespan=lifespan,
    description=(
        "Consulta de **solo lectura** del catálogo (SKUs, ventas, compras y "
        "cajas pendientes).\n\n"
        "📄 **Contexto completo para asistentes (Claude / LLM):** "
        "[`/contexto-api.md`](/contexto-api.md). Markdown con todos los endpoints, "
        "filtros, campos, relaciones entre tablas, recetas y trampas habituales. "
        "Descárgalo y pégalo (o adjúntalo) en la conversación con el asistente.\n\n"
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
        "**Uso recomendado:** hasta **1080 peticiones por minuto**."
    ),
    openapi_tags=tags_metadata,
    contact={"name": "Soporte catálogo", "email": "efrenoscar6@gmail.com"},
    license_info={"name": "Uso privado"},
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _ratelimit_handler(request: Request, exc: RateLimitExceeded):
    # Hay que DEVOLVER la respuesta: una excepción lanzada desde un exception
    # handler no la captura nadie y acabaría en un 500.
    return JSONResponse(status_code=429, content={"detail": "Demasiadas peticiones"})


if settings.cors_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


# ── Contexto para asistentes (sin auth, como /docs) ──────────────────────────
@app.get(
    "/contexto-api.md",
    tags=["Documentación"],
    summary="Contexto de la API para asistentes (Markdown)",
    description="Devuelve un documento Markdown con todo el contexto de la API "
    "(autenticación, endpoints, filtros, campos, relaciones, recetas y trampas) "
    "pensado para proporcionárselo a Claude u otro asistente. Público, como "
    "`/docs`: no contiene datos ni secretos.",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}, "description": "Documento Markdown."}},
)
async def contexto_api():
    return Response(
        content=CONTEXTO_MD,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="contexto_api.md"'},
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
@limiter.shared_limit(settings.rate_limit, scope="global")
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
@limiter.shared_limit(settings.rate_limit, scope="global")
async def refresh(request: Request, body: RefreshIn):
    # Rotación: valida y revoca el refresh usado en una sola sentencia, así dos
    # peticiones simultáneas con el mismo token no pueden canjearlo las dos.
    username = await consume_refresh_token(body.refresh_token)
    if username is None:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")
    user = await get_user(username)
    if user is None or not user["activo"]:
        raise HTTPException(status_code=401, detail="Usuario inactivo o inexistente")
    return await _issue_tokens(username)


@app.post(
    "/auth/logout",
    tags=["Autenticación"],
    summary="Revocar un refresh token",
    description="Revoca el `refresh_token` indicado (cierre de sesión). El access "
    "token sigue siendo válido hasta que caduque (máx. 12 h).",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def logout(request: Request, body: RefreshIn):
    await revoke_refresh_token(body.refresh_token)
    return {"detail": "Refresh token revocado"}


# ─────────────────────────────────────────────────────────────────────────────
#  Routers de las tablas reales del catálogo
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(sku_router.router)
app.include_router(ventas_router.router)
app.include_router(compras_router.router)
app.include_router(cajas_router.router)
