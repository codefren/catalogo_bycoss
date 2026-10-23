"""Endpoints de solo lectura sobre la tabla `sku` (catálogo artículo-color-talla).

Grano: una fila por SKU (artículo-color-talla) Y almacén (`fldIdAlmacen`). Un
mismo SKU aparece tantas veces como almacenes lo tengan.

OJO: las columnas camelCase (`fldTemporada`, `fldIdFamilia`, …) se crearon con
comillas en Postgres, así que en el SQL hay que citarlas: `"fldTemporada"`.
Las columnas en minúscula (`sku`, `talla`, `articulo_descripcion`, `pvp`, …) no
necesitan comillas.

SELECT explícito (nunca `SELECT *`): solo salen de la base las columnas que se
exponen. Quedan fuera, por sensibles o internas: proveedor,
parámetros de reposición (mínimo/máximo/punto de pedido), totales de movimiento
(entradas/salidas/servicio/tránsito) y códigos sin descripción (grupo, subgrupo,
subfamilia, temporada de venta).

Todas las consultas son parametrizadas (bind params): sin inyección SQL. El
orden se elige de una lista blanca, nunca se concatena input del usuario.
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import StringConstraints
from sqlalchemy import text

from db import engine
from schemas import SkuOut, SkuPage
from security import RATE_LIMIT_RESPONSE, limiter, require_jwt
from settings import settings

router = APIRouter(prefix="/api/skus", tags=["SKU — catálogo"])

_SELECT = """
SELECT
    sku,
    "fldIdAlmacen",
    "fldIdArticulo",
    articulo_descripcion,
    "fldTemporada",
    "fldIdFamilia",
    "fldIdSexo",
    "fldReferencia",
    codigo_barras,
    "fldColeccion",
    "fldIdMarca",
    "fldIdColor",
    color_descripcion,
    "fldIdGrupoTallas",
    grupotalla_descripcion,
    talla,
    pvp,
    precio_costo,
    stock_disponible,
    actualizado_en
FROM sku
"""

# Lista blanca de ordenaciones: valor del parámetro -> expresión SQL. Siempre se
# desempata por (sku, almacén) para que la paginación sea estable.
_ORDEN = {
    "sku": "sku",
    "articulo": '"fldIdArticulo", "fldIdColor", talla',
    "pvp": "pvp",
    "stock": "stock_disponible",
    "actualizado": "actualizado_en",
}
_DESEMPATE = 'sku, "fldIdAlmacen"'

# Filtros por lista de valores (se pueden repetir: ?almacen=A&almacen=B):
# parámetro -> columna.
_FILTROS_LISTA = {
    "almacen": '"fldIdAlmacen"',
    "articulo": '"fldIdArticulo"',
    "temporada": '"fldTemporada"',
    "familia": '"fldIdFamilia"',
    "sexo": '"fldIdSexo"',
    "marca": '"fldIdMarca"',
    "coleccion": '"fldColeccion"',
    "color": '"fldIdColor"',
    "grupo_tallas": '"fldIdGrupoTallas"',
    "talla": "talla",
    "codigo_barras": "codigo_barras",
    "referencia": '"fldReferencia"',
}


# Un valor de filtro: texto de hasta 50 caracteres.
Codigo = Annotated[str, StringConstraints(max_length=50)]


def _lista(descripcion: str):
    # max_length aquí limita el nº de valores repetidos (hasta 50 por filtro).
    return Query(None, max_length=50, description=descripcion + " Repetible para varios valores.")


@router.get(
    "",
    response_model=SkuPage,
    summary="Listar SKUs",
    description="Lista paginada del catálogo (una fila por SKU y almacén). "
    "Todos los filtros son opcionales y se combinan con AND. Los filtros de "
    "código admiten **varios valores** repitiendo el parámetro "
    "(`?almacen=00000207&almacen=00000208`), que se combinan con OR. "
    "Filtrar por `articulo` devuelve todas las permutas color/talla de ese "
    "artículo.",
    responses=RATE_LIMIT_RESPONSE,
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def list_skus(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Tamaño de página."),
    offset: int = Query(0, ge=0, description="Desplazamiento."),
    # ── Texto ────────────────────────────────────────────────────────────────
    q: str | None = Query(None, max_length=200, description="Busca en la descripción del artículo (parcial, sin distinguir mayúsculas)."),
    sku_prefijo: str | None = Query(None, max_length=100, description="SKUs que empiezan por este texto."),
    # ── Códigos (repetibles) ─────────────────────────────────────────────────
    almacen: list[Codigo] | None = _lista("Filtra por fldIdAlmacen."),
    articulo: list[Codigo] | None = _lista("Filtra por fldIdArticulo (todas sus permutas color/talla)."),
    temporada: list[Codigo] | None = _lista("Filtra por fldTemporada."),
    familia: list[Codigo] | None = _lista("Filtra por fldIdFamilia."),
    sexo: list[Codigo] | None = _lista("Filtra por fldIdSexo."),
    marca: list[Codigo] | None = _lista("Filtra por fldIdMarca."),
    coleccion: list[Codigo] | None = _lista("Filtra por fldColeccion."),
    color: list[Codigo] | None = _lista("Filtra por fldIdColor."),
    grupo_tallas: list[Codigo] | None = _lista("Filtra por fldIdGrupoTallas."),
    talla: list[Codigo] | None = _lista("Filtra por talla."),
    codigo_barras: list[Codigo] | None = _lista("Filtra por código de barras (EAN)."),
    referencia: list[Codigo] | None = _lista("Filtra por fldReferencia."),
    # ── Rangos ───────────────────────────────────────────────────────────────
    pvp_min: float | None = Query(None, ge=0, description="PVP mínimo (inclusive)."),
    pvp_max: float | None = Query(None, ge=0, description="PVP máximo (inclusive)."),
    stock_min: float | None = Query(None, description="Stock disponible mínimo (inclusive)."),
    stock_max: float | None = Query(None, description="Stock disponible máximo (inclusive)."),
    con_stock: bool = Query(False, description="Si es true, solo filas con stock_disponible > 0."),
    actualizado_desde: datetime | None = Query(None, description="Solo filas actualizadas en o después de esta fecha/hora (ISO 8601). Útil para sincronizaciones incrementales."),
    # ── Orden ────────────────────────────────────────────────────────────────
    orden: Literal["sku", "articulo", "pvp", "stock", "actualizado"] = Query("sku", description="Campo de ordenación."),
    direccion: Literal["asc", "desc"] = Query("asc", description="Sentido de la ordenación."),
    _: dict = Depends(require_jwt),
):
    if pvp_min is not None and pvp_max is not None and pvp_min > pvp_max:
        raise HTTPException(status_code=422, detail="pvp_min no puede ser mayor que pvp_max")
    if stock_min is not None and stock_max is not None and stock_min > stock_max:
        raise HTTPException(status_code=422, detail="stock_min no puede ser mayor que stock_max")

    where: list[str] = []
    params: dict = {}

    if q:
        where.append("articulo_descripcion ILIKE :q")
        params["q"] = f"%{q}%"
    if sku_prefijo:
        where.append("sku LIKE :sku_prefijo")
        # Se escapan los comodines para que el prefijo sea literal.
        escapado = sku_prefijo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["sku_prefijo"] = escapado + "%"

    valores = {
        "almacen": almacen, "articulo": articulo, "temporada": temporada,
        "familia": familia, "sexo": sexo, "marca": marca, "coleccion": coleccion,
        "color": color, "grupo_tallas": grupo_tallas, "talla": talla,
        "codigo_barras": codigo_barras, "referencia": referencia,
    }
    for nombre, lista in valores.items():
        lista = [v for v in (lista or []) if v]
        if lista:
            where.append(f"{_FILTROS_LISTA[nombre]} = ANY(:{nombre})")
            params[nombre] = lista

    if pvp_min is not None:
        where.append("pvp >= :pvp_min")
        params["pvp_min"] = pvp_min
    if pvp_max is not None:
        where.append("pvp <= :pvp_max")
        params["pvp_max"] = pvp_max
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
    items = [SkuOut(**dict(r)) for r in rows]
    return SkuPage(items=items, count=len(items), limit=limit, offset=offset)


@router.get(
    "/{sku}",
    response_model=SkuPage,
    summary="Obtener un SKU (por almacén)",
    description="Devuelve las filas de un SKU concreto, **una por almacén**, "
    "ordenadas por almacén. Con `almacen` se limita a esos almacenes. `404` si "
    "no hay ninguna fila.",
    responses={404: {"description": "SKU no encontrado"}, **RATE_LIMIT_RESPONSE},
)
@limiter.shared_limit(settings.rate_limit, scope="global")
async def get_sku(
    request: Request,
    sku: str,
    almacen: list[Codigo] | None = _lista("Limita a estos fldIdAlmacen."),
    _: dict = Depends(require_jwt),
):
    sql = _SELECT + " WHERE sku = :sku"
    params: dict = {"sku": sku}
    almacenes = [a for a in (almacen or []) if a]
    if almacenes:
        sql += ' AND "fldIdAlmacen" = ANY(:almacen)'
        params["almacen"] = almacenes
    sql += ' ORDER BY "fldIdAlmacen"'

    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="SKU no encontrado")
    items = [SkuOut(**dict(r)) for r in rows]
    return SkuPage(items=items, count=len(items), limit=len(items), offset=0)
