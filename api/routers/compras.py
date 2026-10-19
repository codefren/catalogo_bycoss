"""Endpoints de solo lectura sobre la tabla `compras_maestro` (líneas de compra).

Grano: una fila por artículo-color-talla comprado a un proveedor. La tabla no
tiene PK declarada.

Columnas camelCase citadas en el SQL con comillas (`"fldIdProveedor"`, …); las
columnas en minúscula (`fecha`, `talla`, `cantidad`, `nombre_proveedor`, …) no
necesitan comillas. Todo parametrizado (bind params): sin inyección SQL.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text

from db import engine
from schemas import ComprasPage, CompraOut
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/compras", tags=["Compras — líneas de compra"])


@router.get(
    "",
    response_model=ComprasPage,
    summary="Listar líneas de compra",
    description="Lista paginada de líneas de compra, con filtros opcionales por "
    "rango de fechas, almacén, proveedor, artículo, color, talla, temporada y "
    "familia. Ordena por fecha descendente.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.limit(settings.rate_limit)
async def list_compras(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    fecha_desde: date | None = Query(None, description="Fecha mínima (inclusive), formato YYYY-MM-DD."),
    fecha_hasta: date | None = Query(None, description="Fecha máxima (inclusive), formato YYYY-MM-DD."),
    almacen: str | None = Query(None, max_length=50, description="Filtra por fldIdAlmacen."),
    proveedor: str | None = Query(None, max_length=50, description="Filtra por fldIdProveedor."),
    articulo: str | None = Query(None, max_length=50, description="Filtra por fldIdArticulo."),
    color: str | None = Query(None, max_length=50, description="Filtra por fldIdColor."),
    talla: str | None = Query(None, max_length=50, description="Filtra por talla."),
    temporada: str | None = Query(None, max_length=50, description="Filtra por fldTemporada."),
    familia: str | None = Query(None, max_length=50, description="Filtra por fldIdFamilia."),
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
    if proveedor:
        where.append('"fldIdProveedor" = :proveedor')
        params["proveedor"] = proveedor
    if articulo:
        where.append('"fldIdArticulo" = :articulo')
        params["articulo"] = articulo
    if color:
        where.append('"fldIdColor" = :color')
        params["color"] = color
    if talla:
        where.append("talla = :talla")
        params["talla"] = talla
    if temporada:
        where.append('"fldTemporada" = :temporada')
        params["temporada"] = temporada
    if familia:
        where.append('"fldIdFamilia" = :familia')
        params["familia"] = familia

    sql = "SELECT * FROM compras_maestro"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += ' ORDER BY fecha DESC, "fldIdProveedor", "fldIdArticulo", talla_pos LIMIT :limit OFFSET :offset'
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [CompraOut(**dict(r)) for r in rows]
    return ComprasPage(items=items, count=len(items), limit=limit, offset=offset)
