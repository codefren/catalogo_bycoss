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
from schemas import TicketCabeceraOut, TicketCabeceraPage, TicketLineaOut, TicketPage
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/ventas", tags=["Ventas — líneas de ticket"])

# Cabecera del ticket: `ticket_maestro` tiene una fila por línea y los importes
# de cabecera se repiten idénticos en cada línea del mismo ticket. Se agregan
# por la clave natural (MAX() = valor constante del ticket) para devolverlos una
# sola vez. No se exponen operario/cajera ni códigos internos (igual que la
# línea). Columnas camelCase entrecomilladas; `fecha`/`dto_cabecera` no.
_CABECERA_SELECT = """
SELECT
    "fldIdEmpresa",
    "fldIdAlmacen",
    "fldIdCaja",
    "fldIdTicket",
    MAX(fecha)              AS fecha,
    MAX("fldHora")          AS "fldHora",
    MAX("fldIdCliente")     AS "fldIdCliente",
    MAX("fldIdMoneda")      AS "fldIdMoneda",
    MAX("fldCambio")        AS "fldCambio",
    MAX("fldPrendas")       AS "fldPrendas",
    MAX("fldImporteBruto")  AS "fldImporteBruto",
    MAX("fldImporteDto")    AS "fldImporteDto",
    MAX("fldImporteNeto")   AS "fldImporteNeto",
    MAX("fldCobradoTicket") AS "fldCobradoTicket",
    MAX("fldPteTicket")     AS "fldPteTicket",
    MAX(dto_cabecera)       AS dto_cabecera,
    MAX("fldVales")         AS "fldVales",
    MAX("fldApartados")     AS "fldApartados",
    MAX("fldArreglos")      AS "fldArreglos",
    MAX("fldPromociones")   AS "fldPromociones",
    MAX("fldChequeRegalo")  AS "fldChequeRegalo",
    MAX("fldCupones")       AS "fldCupones",
    MAX("fldEspecial")      AS "fldEspecial"
FROM ticket_maestro
"""
_CABECERA_GROUP_BY = ' GROUP BY "fldIdEmpresa", "fldIdAlmacen", "fldIdCaja", "fldIdTicket"'


@router.get(
    "",
    response_model=TicketPage,
    summary="Listar líneas de venta",
    description="Lista paginada de líneas de ticket, con filtros opcionales por "
    "rango de fechas, almacén, ticket, SKU y cliente. Ordena por fecha "
    "descendente.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
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
    _: dict = Depends(require_jwt),
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
    # Orden total (clave natural de la línea + ctid) para que la paginación sea
    # estable: sin él, las filas empatadas pueden cambiar de página entre consultas.
    sql += (
        ' ORDER BY fecha DESC, "fldIdTicket", "fldLinea", "fldIdEmpresa", "fldIdAlmacen", "fldIdCaja", ctid'
        " LIMIT :limit OFFSET :offset"
    )
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
@limiter.shared_limit(settings.rate_limit, scope="global")
async def get_ticket(
    request: Request,
    empresa: str,
    almacen: str,
    caja: str,
    ticket: str,
    _: dict = Depends(require_jwt),
):
    sql = (
        "SELECT * FROM ticket_maestro "
        'WHERE "fldIdEmpresa" = :empresa AND "fldIdAlmacen" = :almacen '
        'AND "fldIdCaja" = :caja AND "fldIdTicket" = :ticket '
        'ORDER BY "fldLinea", ctid'
    )
    params = {"empresa": empresa, "almacen": almacen, "caja": caja, "ticket": ticket}
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Ticket sin líneas")
    items = [TicketLineaOut(**dict(r)) for r in rows]
    return TicketPage(items=items, count=len(items), limit=len(items), offset=0)


@router.get(
    "/cabeceras",
    response_model=TicketCabeceraPage,
    summary="Listar cabeceras de ticket (totales)",
    description="Lista paginada de cabeceras de ticket: agrega las líneas de "
    "cada ticket en una sola fila con sus totales (importes, prendas, descuentos), "
    "sin duplicarlos por línea. Filtros opcionales por rango de fechas, almacén, "
    "cliente y ticket. Ordena por fecha descendente.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def list_cabeceras(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    fecha_desde: date | None = Query(None, description="Fecha mínima (inclusive), formato YYYY-MM-DD."),
    fecha_hasta: date | None = Query(None, description="Fecha máxima (inclusive), formato YYYY-MM-DD."),
    almacen: str | None = Query(None, max_length=50, description="Filtra por fldIdAlmacen."),
    cliente: str | None = Query(None, max_length=50, description="Filtra por fldIdCliente."),
    ticket: str | None = Query(None, max_length=50, description="Filtra por fldIdTicket."),
    _: dict = Depends(require_jwt),
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
    if cliente:
        where.append('"fldIdCliente" = :cliente')
        params["cliente"] = cliente
    if ticket:
        where.append('"fldIdTicket" = :ticket')
        params["ticket"] = ticket

    sql = _CABECERA_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += _CABECERA_GROUP_BY
    # La clave del GROUP BY completa el orden: una cabecera por ticket, sin empates.
    sql += (
        ' ORDER BY fecha DESC, "fldIdTicket", "fldIdEmpresa", "fldIdAlmacen", "fldIdCaja"'
        " LIMIT :limit OFFSET :offset"
    )
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [TicketCabeceraOut(**dict(r)) for r in rows]
    return TicketCabeceraPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/cabecera/{empresa}/{almacen}/{caja}/{ticket}",
    response_model=TicketCabeceraOut,
    summary="Cabecera de un ticket (totales)",
    description="Devuelve la cabecera (totales) de un ticket por su clave natural "
    "(empresa, almacén, caja, ticket), en una sola fila. `404` si no existe.",
    responses={404: {"description": "Ticket inexistente"}, **RATE_LIMIT_RESPONSE},
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def get_cabecera(
    request: Request,
    empresa: str,
    almacen: str,
    caja: str,
    ticket: str,
    _: dict = Depends(require_jwt),
):
    sql = (
        _CABECERA_SELECT
        + 'WHERE "fldIdEmpresa" = :empresa AND "fldIdAlmacen" = :almacen '
        'AND "fldIdCaja" = :caja AND "fldIdTicket" = :ticket'
        + _CABECERA_GROUP_BY
    )
    params = {"empresa": empresa, "almacen": almacen, "caja": caja, "ticket": ticket}
    async with engine.connect() as conn:
        row = (await conn.execute(text(sql), params)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket inexistente")
    return TicketCabeceraOut(**dict(row))
