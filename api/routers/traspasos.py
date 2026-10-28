"""Endpoints de solo lectura de traspasos (movimientos entre almacenes).

Devuelve cada traspaso **anidado**: cabecera (origen, destino con sus
descripciones, fecha, tipo) + líneas (sku + cantidad). Las líneas se agregan en
la propia consulta con `json_agg`.

La tabla `traspasos` ya viene filtrada por el ETL a traspasos con origen Y
destino entre 00000001 y 00000220 (entre tiendas). Consultas parametrizadas.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from db import engine
from schemas import TraspasoOut, TraspasoPage
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/traspasos", tags=["Traspasos"])

# Cabecera + líneas agregadas en JSON. El WHERE (sobre columnas crudas) y el
# GROUP BY se añaden en cada endpoint.
_SELECT = """
SELECT
    "fldIdTraspaso"  AS traspaso,
    "fldIdOrigen"    AS origen,
    origen_descripcion,
    "fldIdDestino"   AS destino,
    destino_descripcion,
    fecha,
    "fldTipo"        AS tipo,
    json_agg(
        json_build_object('sku', sku, 'cantidad', cantidad)
        ORDER BY "fldLinea", talla
    ) AS lineas
FROM traspasos
"""
_GROUP_BY = (
    ' GROUP BY "fldIdTraspaso", "fldIdOrigen", origen_descripcion, '
    '"fldIdDestino", destino_descripcion, fecha, "fldTipo"'
)


def _to_out(row) -> TraspasoOut:
    d = dict(row)
    lineas = d.get("lineas")
    if isinstance(lineas, str):  # asyncpg devuelve json como texto
        lineas = json.loads(lineas)
    return TraspasoOut(
        traspaso=d["traspaso"],
        origen=d["origen"],
        origen_descripcion=d["origen_descripcion"],
        destino=d["destino"],
        destino_descripcion=d["destino_descripcion"],
        fecha=d["fecha"],
        tipo=d["tipo"],
        lineas=lineas or [],
    )


@router.get(
    "",
    response_model=TraspasoPage,
    summary="Listar traspasos",
    description="Lista paginada de traspasos entre tiendas (origen y destino "
    "entre 00000001 y 00000220), cada uno con su cabecera y sus líneas "
    "(sku + cantidad) anidadas. Filtros opcionales por fecha, origen, destino y "
    "nº de traspaso. Ordena por fecha descendente.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def list_traspasos(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página (nº de traspasos)."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    fecha_desde: str | None = Query(None, description="Fecha inicial inclusive (YYYY-MM-DD)."),
    fecha_hasta: str | None = Query(None, description="Fecha final inclusive (YYYY-MM-DD)."),
    origen: str | None = Query(None, max_length=50, description="Filtra por almacén de origen (fldIdOrigen)."),
    destino: str | None = Query(None, max_length=50, description="Filtra por almacén de destino (fldIdDestino)."),
    traspaso: str | None = Query(None, max_length=50, description="Filtra por nº de traspaso (fldIdTraspaso)."),
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
    if origen:
        where.append('"fldIdOrigen" = :origen')
        params["origen"] = origen
    if destino:
        where.append('"fldIdDestino" = :destino')
        params["destino"] = destino
    if traspaso:
        where.append('"fldIdTraspaso" = :traspaso')
        params["traspaso"] = traspaso

    sql = _SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += _GROUP_BY
    sql += ' ORDER BY fecha DESC NULLS LAST, "fldIdTraspaso" LIMIT :limit OFFSET :offset'
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [_to_out(r) for r in rows]
    return TraspasoPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/{traspaso}",
    response_model=TraspasoOut,
    summary="Obtener un traspaso",
    description="Devuelve un traspaso concreto por su nº, con sus líneas.",
    responses={404: {"description": "Traspaso no encontrado"}, **RATE_LIMIT_RESPONSE},
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def get_traspaso(
    request: Request,
    traspaso: str,
    _: dict = Depends(require_jwt),
):
    sql = _SELECT + ' WHERE "fldIdTraspaso" = :traspaso' + _GROUP_BY
    async with engine.connect() as conn:
        row = (
            await conn.execute(text(sql), {"traspaso": traspaso})
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Traspaso no encontrado")
    return _to_out(row)
