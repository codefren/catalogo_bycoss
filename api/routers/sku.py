"""Endpoints de solo lectura sobre la tabla `sku` (catálogo artículo-color-talla).

OJO: las columnas camelCase (`fldTemporada`, `fldIdFamilia`, …) se crearon con
comillas en Postgres, así que en el SQL hay que citarlas: `"fldTemporada"`.
Las columnas en minúscula (`sku`, `talla`, `articulo_descripcion`,
`stock_disponible`) no necesitan comillas.

Todas las consultas son parametrizadas (bind params): sin inyección SQL.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from db import engine
from schemas import SkuOut, SkuPage
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/skus", tags=["SKU — catálogo"])


@router.get(
    "",
    response_model=SkuPage,
    summary="Listar SKUs",
    description="Lista paginada del catálogo, con filtros opcionales por "
    "temporada, familia, proveedor, marca, color, talla y texto en la "
    "descripción. Ordena por código de SKU.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.limit(settings.rate_limit)
async def list_skus(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    q: str | None = Query(None, max_length=200, description="Busca en la descripción del artículo (parcial, sin distinguir mayúsculas)."),
    temporada: str | None = Query(None, max_length=50, description="Filtra por fldTemporada."),
    familia: str | None = Query(None, max_length=50, description="Filtra por fldIdFamilia."),
    proveedor: str | None = Query(None, max_length=50, description="Filtra por fldIdProveedor."),
    marca: str | None = Query(None, max_length=50, description="Filtra por fldIdMarca."),
    color: str | None = Query(None, max_length=50, description="Filtra por fldIdColor."),
    talla: str | None = Query(None, max_length=50, description="Filtra por talla."),
    con_stock: bool = Query(False, description="Si es true, solo SKUs con stock_disponible > 0."),
    _: dict = Depends(require_jwt),
):
    where: list[str] = []
    params: dict = {}
    if q:
        where.append("articulo_descripcion ILIKE :q")
        params["q"] = f"%{q}%"
    if temporada:
        where.append('"fldTemporada" = :temporada')
        params["temporada"] = temporada
    if familia:
        where.append('"fldIdFamilia" = :familia')
        params["familia"] = familia
    if proveedor:
        where.append('"fldIdProveedor" = :proveedor')
        params["proveedor"] = proveedor
    if marca:
        where.append('"fldIdMarca" = :marca')
        params["marca"] = marca
    if color:
        where.append('"fldIdColor" = :color')
        params["color"] = color
    if talla:
        where.append("talla = :talla")
        params["talla"] = talla
    if con_stock:
        where.append("stock_disponible > 0")

    sql = "SELECT * FROM sku"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sku LIMIT :limit OFFSET :offset"
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [SkuOut(**dict(r)) for r in rows]
    return SkuPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/{sku}",
    response_model=SkuOut,
    summary="Obtener un SKU",
    description="Devuelve una referencia concreta por su código de SKU.",
    responses={404: {"description": "SKU no encontrado"}, **RATE_LIMIT_RESPONSE},
)
@limiter.limit(settings.rate_limit)
async def get_sku(
    request: Request,
    sku: str,
    _: dict = Depends(require_jwt),
):
    async with engine.connect() as conn:
        row = (
            await conn.execute(text("SELECT * FROM sku WHERE sku = :sku"), {"sku": sku})
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="SKU no encontrado")
    return SkuOut(**dict(row))
