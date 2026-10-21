"""Endpoints de solo lectura sobre la tabla `stock` (stock por almacén).

Grano: una fila por artículo-color-talla (`fldIdArticulo`, `fldIdColor`, `talla`)
Y almacén (`fldIdAlmacen`). A diferencia de `sku`, trae la descripción del
almacén (`almacen_descripcion`).

OJO: las columnas camelCase (`fldIdAlmacen`, `fldIdArticulo`, …) se crearon con
comillas en Postgres, así que en el SQL hay que citarlas.

SELECT explícito (nunca `SELECT *`): quedan fuera los totales de movimiento
(entradas/salidas/servicio/tránsito), igual que en `sku`.

Todas las consultas son parametrizadas (bind params): sin inyección SQL. El
orden se elige de una lista blanca, nunca se concatena input del usuario.
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import StringConstraints
from sqlalchemy import text

from db import engine
from schemas import AlmacenesPage, AlmacenOut, StockOut, StockPage
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/stock", tags=["Stock por almacén"])

_SELECT = """
SELECT
    "fldIdAlmacen",
    almacen_descripcion,
    "fldIdArticulo",
    "fldIdColor",
    talla,
    stock_disponible,
    actualizado_en
FROM stock
"""

# Lista blanca de ordenaciones: valor del parámetro -> expresión SQL.
_ORDEN = {
    "almacen": '"fldIdAlmacen"',
    "articulo": '"fldIdArticulo", "fldIdColor", talla',
    "stock": "stock_disponible",
    "actualizado": "actualizado_en",
}
# La tabla no tiene clave única: la clave natural + ctid cierra el orden para que
# la paginación sea estable.
_DESEMPATE = '"fldIdAlmacen", "fldIdArticulo", "fldIdColor", talla, ctid'

# Filtros por lista de valores (se pueden repetir: ?almacen=A&almacen=B):
# parámetro -> columna.
_FILTROS_LISTA = {
    "almacen": '"fldIdAlmacen"',
    "articulo": '"fldIdArticulo"',
    "color": '"fldIdColor"',
    "talla": "talla",
}


# Un valor de filtro: texto de hasta 50 caracteres.
Codigo = Annotated[str, StringConstraints(max_length=50)]


def _lista(descripcion: str):
    # max_length aquí limita el nº de valores repetidos (hasta 50 por filtro).
    return Query(None, max_length=50, description=descripcion + " Repetible para varios valores.")


@router.get(
    "",
    response_model=StockPage,
    summary="Listar stock por almacén",
    description="Lista paginada del stock (una fila por artículo-color-talla y "
    "almacén), con la descripción del almacén. Todos los filtros son opcionales "
    "y se combinan con AND. Los filtros de código admiten **varios valores** "
    "repitiendo el parámetro (`?almacen=00000207&almacen=00000208`), que se "
    "combinan con OR.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def list_stock(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    # ── Códigos (repetibles) ─────────────────────────────────────────────────
    almacen: list[Codigo] | None = _lista("Filtra por fldIdAlmacen."),
    articulo: list[Codigo] | None = _lista("Filtra por fldIdArticulo."),
    color: list[Codigo] | None = _lista("Filtra por fldIdColor."),
    talla: list[Codigo] | None = _lista("Filtra por talla."),
    # ── Texto ────────────────────────────────────────────────────────────────
    almacen_nombre: str | None = Query(None, max_length=200, description="Busca en la descripción del almacén (parcial, sin distinguir mayúsculas)."),
    # ── Rangos ───────────────────────────────────────────────────────────────
    stock_min: float | None = Query(None, description="Stock disponible mínimo (inclusive)."),
    stock_max: float | None = Query(None, description="Stock disponible máximo (inclusive)."),
    con_stock: bool = Query(False, description="Si es true, solo filas con stock_disponible > 0."),
    actualizado_desde: datetime | None = Query(None, description="Solo filas actualizadas en o después de esta fecha/hora (ISO 8601). Útil para sincronizaciones incrementales."),
    # ── Orden ────────────────────────────────────────────────────────────────
    orden: Literal["almacen", "articulo", "stock", "actualizado"] = Query("almacen", description="Campo de ordenación."),
    direccion: Literal["asc", "desc"] = Query("asc", description="Sentido de la ordenación."),
    _: dict = Depends(require_jwt),
):
    if stock_min is not None and stock_max is not None and stock_min > stock_max:
        raise HTTPException(status_code=422, detail="stock_min no puede ser mayor que stock_max")

    where: list[str] = []
    params: dict = {}

    valores = {"almacen": almacen, "articulo": articulo, "color": color, "talla": talla}
    for nombre, lista in valores.items():
        lista = [v for v in (lista or []) if v]
        if lista:
            where.append(f"{_FILTROS_LISTA[nombre]} = ANY(:{nombre})")
            params[nombre] = lista

    if almacen_nombre:
        where.append("almacen_descripcion ILIKE :almacen_nombre")
        params["almacen_nombre"] = f"%{almacen_nombre}%"
    if stock_min is not None:
        where.append("stock_disponible >= :stock_min")
        params["stock_min"] = stock_min
    if stock_max is not None:
        where.append("stock_disponible <= :stock_max")
        params["stock_max"] = stock_max
    if con_stock:
        where.append("stock_disponible > 0")
    if actualizado_desde is not None:
        where.append("actualizado_en >= :actualizado_desde")
        # La columna es timestamp SIN zona: se compara la hora tal cual.
        params["actualizado_desde"] = actualizado_desde.replace(tzinfo=None)

    sql = _SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sentido = "DESC" if direccion == "desc" else "ASC"
    columnas = ", ".join(f"{c.strip()} {sentido} NULLS LAST" for c in _ORDEN[orden].split(","))
    sql += f" ORDER BY {columnas}, {_DESEMPATE} LIMIT :limit OFFSET :offset"
    params.update(limit=limit, offset=offset)

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    items = [StockOut(**dict(r)) for r in rows]
    return StockPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/almacenes",
    response_model=AlmacenesPage,
    summary="Listar almacenes",
    description="Todos los almacenes que aparecen en la tabla de stock, con su "
    "descripción, ordenados por código. Sin paginar.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def list_almacenes(
    request: Request,
    _: dict = Depends(require_jwt),
):
    # Si un almacén tuviera varias descripciones, se toma la mayor (determinista).
    sql = (
        'SELECT "fldIdAlmacen", MAX(almacen_descripcion) AS almacen_descripcion '
        'FROM stock GROUP BY "fldIdAlmacen" ORDER BY "fldIdAlmacen"'
    )
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql))).mappings().all()
    items = [AlmacenOut(**dict(r)) for r in rows]
    return AlmacenesPage(items=items, count=len(items), limit=len(items), offset=0)
