"""Tabla `public.stock` — stock por (almacen, articulo, color, talla) con el
nombre del almacen. Porta bycos_pg_exports/stock.py. Modo: overwrite.

Solo se exportan filas con algun movimiento (SOLO_FILAS_CON_STOCK).
"""
from __future__ import annotations

RNG = range(1, 16)

_STOCK_COLS = (
    ["fldIdAlmacen", "fldIdArticulo", "fldIdColor"]
    + [f"fldEntradas{i}" for i in RNG]
    + [f"fldSalidas{i}" for i in RNG]
    + [f"fldServicio{i}" for i in RNG]
    + [f"fldTransito{i}" for i in RNG]
)
_GT_COLS = ["fldIdGrupoTallas"] + [f"fldTalla{i}" for i in RNG]

SOURCES = {
    "stock":      f"SELECT {', '.join(_STOCK_COLS)} FROM dbo.tbdStock",
    "articulo1":  "SELECT fldIdArticulo, fldIdGrupoTallas FROM dbo.tbdArticulos0",
    "grupotalla": f"SELECT {', '.join(_GT_COLS)} FROM dbo.tbdGruposTallas",
    "almacenes":  "SELECT fldIdAlmacen, fldDescripcion FROM dbo.tbdAlmacenes",
}

TARGET = "public.stock"
TARGET_DDL = """
CREATE TABLE IF NOT EXISTS public.stock (
    "fldIdAlmacen" text,
    almacen_descripcion text,
    "fldIdArticulo" text,
    "fldIdColor" text,
    talla text,
    total_entradas double precision,
    total_salidas double precision,
    total_servicio double precision,
    total_transito double precision,
    stock_disponible double precision,
    actualizado_en timestamp without time zone NOT NULL
)
"""
TARGET_COLUMNS = [
    "fldIdAlmacen", "almacen_descripcion", "fldIdArticulo", "fldIdColor",
    "talla", "total_entradas", "total_salidas", "total_servicio",
    "total_transito", "stock_disponible",
]
KEYS = ["fldIdAlmacen", "fldIdArticulo", "fldIdColor", "talla"]


def _num(col: str) -> str:
    return f"NULLIF(btrim({col}), '')::numeric"


def build_select() -> str:
    stock_values = ",\n            ".join(
        f"({i}, {_num(f'fldentradas{i}')}, {_num(f'fldsalidas{i}')}, "
        f"{_num(f'fldservicio{i}')}, {_num(f'fldtransito{i}')})"
        for i in RNG
    )
    gt_long = " UNION ALL ".join(
        f"SELECT fldidgrupotallas, {i} AS posicion, fldtalla{i} AS talla "
        f"FROM raw.grupotalla WHERE fldtalla{i} IS NOT NULL AND fldtalla{i} <> ''"
        for i in RNG
    )
    return f"""
WITH stock_unpivoted AS (
    SELECT s.fldidalmacen, s.fldidarticulo, s.fldidcolor,
           u.talla_idx, u.entradas, u.salidas, u.servicio, u.transito
    FROM raw.stock s
    CROSS JOIN LATERAL (VALUES
            {stock_values}
    ) AS u(talla_idx, entradas, salidas, servicio, transito)
),
gt_long AS ({gt_long})
SELECT
    su.fldidalmacen,
    a.flddescripcion AS almacen_descripcion,
    su.fldidarticulo,
    su.fldidcolor,
    gt.talla,
    SUM(COALESCE(su.entradas, 0)) AS total_entradas,
    SUM(COALESCE(su.salidas, 0))  AS total_salidas,
    SUM(COALESCE(su.servicio, 0)) AS total_servicio,
    SUM(COALESCE(su.transito, 0)) AS total_transito,
    SUM(COALESCE(su.entradas, 0)) - SUM(COALESCE(su.salidas, 0))
        - SUM(COALESCE(su.servicio, 0)) AS stock_disponible
FROM stock_unpivoted su
JOIN raw.articulo1 a1 ON su.fldidarticulo = a1.fldidarticulo
JOIN gt_long gt ON a1.fldidgrupotallas = gt.fldidgrupotallas
               AND su.talla_idx = gt.posicion
LEFT JOIN raw.almacenes a ON su.fldidalmacen = a.fldidalmacen
GROUP BY su.fldidalmacen, a.flddescripcion, su.fldidarticulo, su.fldidcolor, gt.talla
HAVING SUM(COALESCE(su.entradas, 0)) > 0 OR SUM(COALESCE(su.salidas, 0)) > 0
    OR SUM(COALESCE(su.servicio, 0)) > 0 OR SUM(COALESCE(su.transito, 0)) > 0
"""
