"""Endpoints de solo lectura sobre la tabla `cajas_pendientes`.

Cajas/envíos pendientes de llegada a tienda. Grano: una fila por
artículo-color-talla dentro de una caja.

En el origen TODAS las columnas son `text` (PascalCase, con el typo `DispathNote`).
Aquí se normaliza: el SELECT es explícito con alias snake_case (nunca `SELECT *`),
así entregamos claves limpias y Pydantic tipa `total_prendas`/`cantidad` como
enteros. Las fechas se dejan como texto (mismo valor del origen) hasta confirmar
su formato. Todo parametrizado (bind params): sin inyección SQL.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from db import engine
from schemas import CajaPendienteOut, CajasPendientesPage
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/cajas-pendientes", tags=["Cajas pendientes"])

# SELECT explícito: columna de origen (PascalCase, entrecomillada) -> alias limpio.
# Se corrige de paso el typo del origen (DispathNote -> dispatch_note).
_SELECT = """
SELECT
    "CodCliente"     AS cod_cliente,
    "Tienda"         AS tienda,
    "NombreTienda"   AS nombre_tienda,
    "DispathNote"    AS dispatch_note,
    "FechaSalida"    AS fecha_salida,
    "FechaLLegada"   AS fecha_llegada,
    "CodigoCaja"     AS codigo_caja,
    "NoBulto"        AS no_bulto,
    "TotalPrendas"   AS total_prendas,
    "NoPedido"       AS no_pedido,
    "NoEnvio"        AS no_envio,
    "EAN"            AS ean,
    "Articulo"       AS articulo,
    "Color"          AS color,
    "Talla"          AS talla,
    "Descri_Art"     AS descripcion_articulo,
    "Descri_Color"   AS descripcion_color,
    "Marca"          AS marca,
    "Familia"        AS familia,
    "Descri_Familia" AS descripcion_familia,
    "Cantidad"       AS cantidad
FROM cajas_pendientes
"""


@router.get(
    "",
    response_model=CajasPendientesPage,
    summary="Listar líneas de cajas pendientes",
    description="Lista paginada de líneas de caja pendientes de llegada a tienda, "
    "con filtros opcionales por tienda, cliente, artículo, EAN, caja, pedido, "
    "envío y albarán. Ordena por fecha de salida descendente.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.limit(settings.rate_limit)
async def list_cajas_pendientes(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    tienda: str | None = Query(None, max_length=50, description="Filtra por Tienda."),
    cliente: str | None = Query(None, max_length=50, description="Filtra por CodCliente."),
    articulo: str | None = Query(None, max_length=50, description="Filtra por Articulo."),
    ean: str | None = Query(None, max_length=50, description="Filtra por EAN."),
    caja: str | None = Query(None, max_length=50, description="Filtra por CodigoCaja."),
    pedido: str | None = Query(None, max_length=50, description="Filtra por NoPedido."),
    envio: str | None = Query(None, max_length=50, description="Filtra por NoEnvio."),
    dispatch_note: str | None = Query(None, max_length=50, description="Filtra por el albarán (DispathNote)."),
    _: dict = Depends(require_jwt),
):
    where: list[str] = []
    params: dict = {}
    if tienda:
        where.append('"Tienda" = :tienda')
        params["tienda"] = tienda
    if cliente:
        where.append('"CodCliente" = :cliente')
        params["cliente"] = cliente
    if articulo:
        where.append('"Articulo" = :articulo')
        params["articulo"] = articulo
    if ean:
        where.append('"EAN" = :ean')
        params["ean"] = ean
    if caja:
        where.append('"CodigoCaja" = :caja')
        params["caja"] = caja
    if pedido:
        where.append('"NoPedido" = :pedido')
        params["pedido"] = pedido
    if envio:
        where.append('"NoEnvio" = :envio')
        params["envio"] = envio
    if dispatch_note:
        where.append('"DispathNote" = :dispatch_note')
        params["dispatch_note"] = dispatch_note

    sql = _SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += ' ORDER BY "FechaSalida" DESC, "CodigoCaja", "Articulo", "Talla" LIMIT :limit OFFSET :offset'
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [CajaPendienteOut(**dict(r)) for r in rows]
    return CajasPendientesPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/caja/{codigo_caja}",
    response_model=CajasPendientesPage,
    summary="Líneas de una caja",
    description="Devuelve todas las líneas de una caja concreta por su CodigoCaja, "
    "ordenadas por artículo y talla.",
    responses={404: {"description": "Caja sin líneas"}, **RATE_LIMIT_RESPONSE},
)
@limiter.limit(settings.rate_limit)
async def get_caja(
    request: Request,
    codigo_caja: str,
    _: dict = Depends(require_jwt),
):
    sql = _SELECT + ' WHERE "CodigoCaja" = :caja ORDER BY "Articulo", "Talla"'
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), {"caja": codigo_caja})).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Caja sin líneas")
    items = [CajaPendienteOut(**dict(r)) for r in rows]
    return CajasPendientesPage(items=items, count=len(items), limit=len(items), offset=0)
