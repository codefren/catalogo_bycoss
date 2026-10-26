"""Tabla `public.sku` — catálogo por (almacen, articulo, color, talla).

Porta a Postgres el job Databricks bycos_pg_exports/sku.py:
  SQL Server (tbdStock, tbdArticulos0, tbdArticulos5, tbdColores,
  tbdGruposTallas, tbdArticulosTarifas) -> public.sku.

El stock crudo tiene 15 posiciones por fila (fldEntradas1..15, etc.); se hace
unpivot a grano talla, se mapea la etiqueta de talla con el grupo de tallas del
artículo, se agregan las medidas y se cruzan los precios (tarifa 10 = pvp,
tarifa 99 = precio_costo). Modo: espejo (overwrite).
"""
from __future__ import annotations

RNG = range(1, 16)

# ── Fuentes en SQL Server (solo las columnas necesarias; nada de SELECT *) ────
_STOCK_COLS = (
    ["fldIdAlmacen", "fldIdArticulo", "fldIdColor"]
    + [f"fldEntradas{i}" for i in RNG]
    + [f"fldSalidas{i}" for i in RNG]
    + [f"fldServicio{i}" for i in RNG]
    + [f"fldTransito{i}" for i in RNG]
)
_ART0_COLS = [
    "fldIdArticulo", "fldDescripcion", "fldIdGrupoTallas", "fldTemporada",
    "fldIdFamilia", "fldIdProveedor", "fldReferencia", "fldIdCodigoBarras",
    "fldColeccion", "fldMinimoStock", "fldMaximoStock", "fldPuntoPedido",
]
_ART5_COLS = [
    "fldIdArticulo", "fldIdMarca", "fldIdSexo", "fldIdGrupo", "fldIdSubgrupo",
    "fldIdSubfamilia", "fldidTemporadaVenta",
]
_GT_COLS = ["fldIdGrupoTallas", "fldDescripcion"] + [f"fldTalla{i}" for i in RNG]
_AT_COLS = ["fldIdArticulo", "fldIdTarifa"] + [f"fldTalla{i}" for i in RNG]

SOURCES = {
    "stock":          f"SELECT {', '.join(_STOCK_COLS)} FROM dbo.tbdStock",
    "articulo1":      f"SELECT {', '.join(_ART0_COLS)} FROM dbo.tbdArticulos0",
    "articulo5":      f"SELECT {', '.join(_ART5_COLS)} FROM dbo.tbdArticulos5",
    "colores":        "SELECT fldIdColor, fldDescripcion FROM dbo.tbdColores",
    "grupotalla":     f"SELECT {', '.join(_GT_COLS)} FROM dbo.tbdGruposTallas",
    "articulo_tarifa": f"SELECT {', '.join(_AT_COLS)} FROM dbo.tbdArticulosTarifas",
}

# ── Esquema destino (coincide con el public.sku que ya sirve la API) ──────────
TARGET = "public.sku"
TARGET_DDL = """
CREATE TABLE IF NOT EXISTS public.sku (
    sku text,
    "fldIdAlmacen" text,
    "fldIdArticulo" text,
    articulo_descripcion text,
    "fldTemporada" text,
    "fldIdFamilia" text,
    "fldIdProveedor" text,
    "fldReferencia" text,
    codigo_barras text,
    "fldColeccion" text,
    "fldMinimoStock" double precision,
    "fldMaximoStock" double precision,
    "fldPuntoPedido" double precision,
    "fldIdMarca" text,
    "fldIdSexo" text,
    "fldIdGrupo" text,
    "fldIdSubgrupo" text,
    "fldIdSubfamilia" text,
    "fldidTemporadaVenta" text,
    "fldIdColor" text,
    color_descripcion text,
    "fldIdGrupoTallas" text,
    grupotalla_descripcion text,
    talla text,
    pvp double precision,
    precio_costo double precision,
    total_entradas double precision,
    total_salidas double precision,
    total_servicio double precision,
    total_transito double precision,
    stock_disponible double precision,
    actualizado_en timestamp without time zone NOT NULL
)
"""

# Columnas destino EN ORDEN (sin actualizado_en, que se añade al cargar). El
# SELECT de build_select() devuelve exactamente estas columnas en este orden.
TARGET_COLUMNS = [
    "sku", "fldIdAlmacen", "fldIdArticulo", "articulo_descripcion",
    "fldTemporada", "fldIdFamilia", "fldIdProveedor", "fldReferencia",
    "codigo_barras", "fldColeccion", "fldMinimoStock", "fldMaximoStock",
    "fldPuntoPedido", "fldIdMarca", "fldIdSexo", "fldIdGrupo", "fldIdSubgrupo",
    "fldIdSubfamilia", "fldidTemporadaVenta", "fldIdColor", "color_descripcion",
    "fldIdGrupoTallas", "grupotalla_descripcion", "talla", "pvp", "precio_costo",
    "total_entradas", "total_salidas", "total_servicio", "total_transito",
    "stock_disponible",
]
KEYS = ["sku"]


def _num(col: str) -> str:
    """Casteo robusto texto -> numeric (vacío/espacios -> NULL)."""
    return f"NULLIF(btrim({col}), '')::numeric"


def build_select() -> str:
    """SQL de transformación: raw.* -> filas de public.sku (sin actualizado_en)."""
    # Unpivot del stock: una fila por (almacen, articulo, color, posicion 1-15).
    stock_values = ",\n            ".join(
        f"({i}, {_num(f'fldentradas{i}')}, {_num(f'fldsalidas{i}')}, "
        f"{_num(f'fldservicio{i}')}, {_num(f'fldtransito{i}')})"
        for i in RNG
    )
    # Etiqueta de talla segun la posicion (desde el grupo de tallas del articulo).
    talla_case = "CASE su.talla_idx " + " ".join(
        f"WHEN {i} THEN g.fldtalla{i}" for i in RNG
    ) + " END"
    # Unpivot de tarifas: (articulo, tarifa, posicion, precio).
    at_long = " UNION ALL ".join(
        f"SELECT fldidarticulo, fldidtarifa, {i} AS posicion, "
        f"{_num(f'fldtalla{i}')} AS precio FROM raw.articulo_tarifa "
        f"WHERE {_num(f'fldtalla{i}')} > 0"
        for i in RNG
    )
    # Unpivot del grupo de tallas: (grupo, posicion, talla).
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
),
articulo_color_talla_stock AS (
    SELECT sm.fldidalmacen, sm.fldidarticulo, sm.articulo_descripcion,
           sm.fldidcolor, co.flddescripcion AS color_descripcion,
           sm.fldidgrupotallas, sm.grupotalla_descripcion, sm.talla,
           SUM(COALESCE(sm.entradas, 0)) AS total_entradas,
           SUM(COALESCE(sm.salidas, 0))  AS total_salidas,
           SUM(COALESCE(sm.servicio, 0)) AS total_servicio,
           SUM(COALESCE(sm.transito, 0)) AS total_transito,
           SUM(COALESCE(sm.entradas, 0)) - SUM(COALESCE(sm.salidas, 0))
               - SUM(COALESCE(sm.servicio, 0)) AS stock_disponible
    FROM stock_mapped sm
    LEFT JOIN raw.colores co ON sm.fldidcolor = co.fldidcolor
    WHERE sm.talla IS NOT NULL AND sm.talla <> ''
    GROUP BY sm.fldidalmacen, sm.fldidarticulo, sm.articulo_descripcion,
             sm.fldidcolor, co.flddescripcion, sm.fldidgrupotallas,
             sm.grupotalla_descripcion, sm.talla
),
at_long AS ({at_long}),
gt_long AS ({gt_long}),
precios AS (
    SELECT tar.fldidarticulo, gt.talla,
           MAX(CASE WHEN tar.fldidtarifa = '10' THEN tar.precio END) AS pvp,
           MAX(CASE WHEN tar.fldidtarifa = '99' THEN tar.precio END) AS precio_costo
    FROM at_long tar
    JOIN raw.articulo1 a1 ON tar.fldidarticulo = a1.fldidarticulo
    JOIN gt_long gt ON a1.fldidgrupotallas = gt.fldidgrupotallas
                   AND tar.posicion = gt.posicion
    GROUP BY tar.fldidarticulo, gt.talla
)
SELECT
    CONCAT_WS('-', s.fldidalmacen, s.fldidarticulo, s.fldidcolor, s.talla) AS sku,
    s.fldidalmacen,
    s.fldidarticulo,
    s.articulo_descripcion,
    a1.fldtemporada,
    a1.fldidfamilia,
    a1.fldidproveedor,
    a1.fldreferencia,
    a1.fldidcodigobarras AS codigo_barras,
    a1.fldcoleccion,
    {_num('a1.fldminimostock')} AS "fldMinimoStock",
    {_num('a1.fldmaximostock')} AS "fldMaximoStock",
    {_num('a1.fldpuntopedido')} AS "fldPuntoPedido",
    a5.fldidmarca,
    a5.fldidsexo,
    a5.fldidgrupo,
    a5.fldidsubgrupo,
    a5.fldidsubfamilia,
    a5.fldidtemporadaventa,
    s.fldidcolor,
    s.color_descripcion,
    s.fldidgrupotallas,
    s.grupotalla_descripcion,
    s.talla,
    p.pvp,
    p.precio_costo,
    s.total_entradas,
    s.total_salidas,
    s.total_servicio,
    s.total_transito,
    s.stock_disponible
FROM articulo_color_talla_stock s
LEFT JOIN raw.articulo1 a1 ON s.fldidarticulo = a1.fldidarticulo
LEFT JOIN raw.articulo5 a5 ON s.fldidarticulo = a5.fldidarticulo
LEFT JOIN precios p ON s.fldidarticulo = p.fldidarticulo AND s.talla = p.talla
"""
