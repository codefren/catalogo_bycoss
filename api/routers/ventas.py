"""Endpoints de solo lectura sobre la tabla `ticket_maestro` (líneas de venta).

Grano: una fila por LÍNEA de ticket (no por ticket). La clave natural de un
ticket es (fldIdEmpresa, fldIdAlmacen, fldIdCaja, fldIdTicket) y la línea añade
fldLinea. La tabla no tiene PK declarada.

Columnas camelCase citadas en el SQL; `fecha`, `sku`, `id_cierre`, etc. en
minúscula no necesitan comillas. Todo parametrizado: sin inyección SQL.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from db import engine
from schemas import TicketLineaOut, TicketPage
from security import RATE_LIMIT_RESPONSE, limiter, require_api_key
from settings import settings

router = APIRouter(prefix="/api/ventas", tags=["Ventas — líneas de ticket"])


@router.get(
    "",
    response_model=TicketPage,
    summary="Listar líneas de venta",
    description="Lista paginada de líneas de ticket, con filtros opcionales por "
    "rango de fechas, almacén, ticket, SKU y cliente. Ordena por fecha "
    "descendente.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.limit(settings.rate_limit)
async def list_ventas(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    fecha_desde: date | None = Query(None, description="Fecha mínima (inclusive), formato YYYY-MM-DD."),
    fecha_hasta: date | None = Query(None, description="Fecha máxima (inclusive), formato YYYY-MM-DD."),
    almacen: str | None = Query(None, max_length=50, description="Filtra por fldIdAlmacen."),
    ticket: str | None = Query(None, max_length=50, description="Filtra por fldIdTicket."),
    sku: str | None = Query(None, max_length=100, description="Filtra por SKU vendido."),
    cliente: str | None = Query(None, max_length=50, description="Filtra por fldIdCliente."),
    _: str = Depends(require_api_key),
):
    where: list[str] = []
    params: dict = {}
    if fecha_desde:
        where.append("fecha >= :fecha_desde")
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        where.append("fecha <= :fecha_hasta")
        params["fecha_hasta"] = fecha_hasta
    if almacen:
        where.append('"fldIdAlmacen" = :almacen')
        params["almacen"] = almacen
    if ticket:
        where.append('"fldIdTicket" = :ticket')
        params["ticket"] = ticket
    if sku:
        where.append("sku = :sku")
        params["sku"] = sku
    if cliente:
        where.append('"fldIdCliente" = :cliente')
        params["cliente"] = cliente

    sql = "SELECT * FROM ticket_maestro"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += ' ORDER BY fecha DESC, "fldIdTicket", "fldLinea" LIMIT :limit OFFSET :offset'
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [TicketLineaOut(**dict(r)) for r in rows]
    return TicketPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/ticket/{empresa}/{almacen}/{caja}/{ticket}",
    response_model=TicketPage,
    summary="Líneas de un ticket",
    description="Devuelve todas las líneas de un ticket identificado por su "
    "clave natural (empresa, almacén, caja, ticket), ordenadas por línea.",
    responses={404: {"description": "Ticket sin líneas"}, **RATE_LIMIT_RESPONSE},
)
@limiter.limit(settings.rate_limit)
async def get_ticket(
    request: Request,
    empresa: str,
    almacen: str,
    caja: str,
    ticket: str,
    _: str = Depends(require_api_key),
):
    sql = (
        "SELECT * FROM ticket_maestro "
        'WHERE "fldIdEmpresa" = :empresa AND "fldIdAlmacen" = :almacen '
        'AND "fldIdCaja" = :caja AND "fldIdTicket" = :ticket '
        'ORDER BY "fldLinea"'
    )
    params = {"empresa": empresa, "almacen": almacen, "caja": caja, "ticket": ticket}
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Ticket sin líneas")
    items = [TicketLineaOut(**dict(r)) for r in rows]
    return TicketPage(items=items, count=len(items), limit=len(items), offset=0)
