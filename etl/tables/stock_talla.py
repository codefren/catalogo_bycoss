"""Tabla `public.stock_talla` — stock por (almacen, articulo, color, talla) con
descripciones de almacen, articulo y grupo de tallas. Porta
bycos_pg_exports/stock_talla.py. Modo: overwrite (carga todo, sin filtrar).
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
_GT_COLS = ["fldIdGrupoTallas", "fldDescripcion"] + [f"fldTalla{i}" for i in RNG]

SOURCES = {
    "stock":      f"SELECT {', '.join(_STOCK_COLS)} FROM dbo.tbdStock",
    "articulo1":  "SELECT fldIdArticulo, fldDescripcion, fldIdGrupoTallas FROM dbo.tbdArticulos0",
    "grupotalla": f"SELECT {', '.join(_GT_COLS)} FROM dbo.tbdGruposTallas",
    "almacenes":  "SELECT fldIdAlmacen, fldDescripcion FROM dbo.tbdAlmacenes",
}

TARGET = "public.stock_talla"
TARGET_DDL = """
CREATE TABLE IF NOT EXISTS public.stock_talla (
    "fldIdAlmacen" text,
    almacen_descripcion text,
    "fldIdArticulo" text,
    articulo_descripcion text,
    "fldIdColor" text,
    "fldIdGrupoTallas" text,
    grupotalla_descripcion text,
    talla text,
    entradas double precision,
    salidas double precision,
    servicio double precision,
    transito double precision,
    stock_disponible double precision,
    actualizado_en timestamp without time zone NOT NULL
)
"""
TARGET_COLUMNS = [
    "fldIdAlmacen", "almacen_descripcion", "fldIdArticulo", "articulo_descripcion",
    "fldIdColor", "fldIdGrupoTallas", "grupotalla_descripcion", "talla",
    "entradas", "salidas", "servicio", "transito", "stock_disponible",
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
    talla_case = "CASE su.talla_idx " + " ".join(
        f"WHEN {i} THEN g.fldtalla{i}" for i in RNG
    ) + " END"
    return f"""
WITH stock_unpivoted AS (
    SELECT s.fldidalmacen, s.fldidarticulo, s.fldidcolor,
           u.talla_idx, u.entradas, u.salidas, u.servicio, u.transito
    FROM raw.stock s
    CROSS JOIN LATERAL (VALUES
            {stock_values}
    ) AS u(talla_idx, entradas, salidas, servicio, transito)
),
stock_mapped AS (
    SELECT su.fldidalmacen, su.fldidarticulo, su.fldidcolor,
           {talla_case} AS talla,
           su.entradas, su.salidas, su.servicio, su.transito,
           a1.flddescripcion AS articulo_descripcion,
           a1.fldidgrupotallas,
           g.flddescripcion AS grupotalla_descripcion
    FROM stock_unpivoted su
    JOIN raw.articulo1 a1 ON su.fldidarticulo = a1.fldidarticulo
    JOIN raw.grupotalla g ON a1.fldidgrupotallas = g.fldidgrupotallas
)
SELECT
    sm.fldidalmacen,
    al.flddescripcion AS almacen_descripcion,
    sm.fldidarticulo,
    sm.articulo_descripcion,
    sm.fldidcolor,
    sm.fldidgrupotallas,
    sm.grupotalla_descripcion,
    sm.talla,
    SUM(COALESCE(sm.entradas, 0)) AS entradas,
    SUM(COALESCE(sm.salidas, 0))  AS salidas,
    SUM(COALESCE(sm.servicio, 0)) AS servicio,
    SUM(COALESCE(sm.transito, 0)) AS transito,
    SUM(COALESCE(sm.entradas, 0)) - SUM(COALESCE(sm.salidas, 0))
        - SUM(COALESCE(sm.servicio, 0)) AS stock_disponible
FROM stock_mapped sm
LEFT JOIN raw.almacenes al ON sm.fldidalmacen = al.fldidalmacen
WHERE sm.talla IS NOT NULL AND sm.talla <> ''
GROUP BY sm.fldidalmacen, al.flddescripcion, sm.fldidarticulo,
         sm.articulo_descripcion, sm.fldidcolor, sm.fldidgrupotallas,
         sm.grupotalla_descripcion, sm.talla
"""
