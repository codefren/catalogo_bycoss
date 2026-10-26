"""Tabla `public.compras_maestro` — una fila por compra+articulo+color+talla.
Porta bycos_pg_exports/compras_talla.py. Modo: overwrite.

Unpivot de fldCantidad1-15 y fldAcumulado1-15, mapeo de talla por grupo de
tallas, enriquecido con proveedor y articulo.
"""
from __future__ import annotations

RNG = range(1, 16)

_COMPRAS_COLS = (
    ["fldIdEmpresa", "fldIdAlmacen", "fldIdProveedor", "fldFecha",
     "fldIdArticulo", "fldIdColor", "fldIdMoneda", "fldCambio"]
    + [f"fldCantidad{i}" for i in RNG]
    + [f"fldAcumulado{i}" for i in RNG]
)
_GT_COLS = ["fldIdGrupoTallas", "fldDescripcion"] + [f"fldTalla{i}" for i in RNG]

SOURCES = {
    "compras":     f"SELECT {', '.join(_COMPRAS_COLS)} FROM dbo.tbdEstCompras",
    "articulo1":   "SELECT fldIdArticulo, fldDescripcion, fldTemporada, "
                   "fldIdFamilia, fldIdGrupoTallas FROM dbo.tbdArticulos0",
    "grupotalla":  f"SELECT {', '.join(_GT_COLS)} FROM dbo.tbdGruposTallas",
    "proveedores": "SELECT fldIdProveedor, fldNombreFiscal FROM dbo.tbdProveedores",
}

TARGET = "public.compras_maestro"
TARGET_DDL = """
CREATE TABLE IF NOT EXISTS public.compras_maestro (
    "fldIdEmpresa" text,
    "fldIdAlmacen" text,
    "fldIdProveedor" text,
    nombre_proveedor text,
    fecha date,
    "fldIdArticulo" text,
    "fldIdColor" text,
    talla_pos integer,
    talla text,
    cantidad double precision,
    acumulado double precision,
    "fldIdMoneda" text,
    "fldCambio" double precision,
    descripcion_articulo text,
    "fldTemporada" text,
    "fldIdFamilia" text,
    "fldIdGrupoTallas" text,
    descripcion_grupo_tallas text,
    actualizado_en timestamp without time zone NOT NULL
)
"""
TARGET_COLUMNS = [
    "fldIdEmpresa", "fldIdAlmacen", "fldIdProveedor", "nombre_proveedor",
    "fecha", "fldIdArticulo", "fldIdColor", "talla_pos", "talla", "cantidad",
    "acumulado", "fldIdMoneda", "fldCambio", "descripcion_articulo",
    "fldTemporada", "fldIdFamilia", "fldIdGrupoTallas", "descripcion_grupo_tallas",
]
KEYS = ["fldIdEmpresa", "fldIdAlmacen", "fldIdProveedor", "fldIdArticulo",
        "fldIdColor", "talla_pos", "fecha"]


def _num(col: str) -> str:
    return f"NULLIF(btrim({col}), '')::numeric"


def build_select() -> str:
    compras_values = ",\n            ".join(
        f"({i}, {_num(f'fldcantidad{i}')}, {_num(f'fldacumulado{i}')})"
        for i in RNG
    )
    talla_case = "CASE cu.talla_pos " + " ".join(
        f"WHEN {i} THEN g.fldtalla{i}" for i in RNG
    ) + " END"
    return f"""
WITH compras_unpivoted AS (
    SELECT c.fldidempresa, c.fldidalmacen, c.fldidproveedor, c.fldfecha,
           c.fldidarticulo, c.fldidcolor, c.fldidmoneda, c.fldcambio,
           u.talla_pos, u.cantidad, u.acumulado
    FROM raw.compras c
    CROSS JOIN LATERAL (VALUES
            {compras_values}
    ) AS u(talla_pos, cantidad, acumulado)
    WHERE u.cantidad <> 0 OR u.acumulado <> 0
),
compras_mapped AS (
    SELECT cu.fldidempresa, cu.fldidalmacen, cu.fldidproveedor, cu.fldfecha,
           cu.fldidarticulo, cu.fldidcolor, cu.fldidmoneda, cu.fldcambio,
           cu.talla_pos,
           {talla_case} AS talla,
           cu.cantidad, cu.acumulado,
           a1.flddescripcion AS descripcion_articulo,
           a1.fldtemporada, a1.fldidfamilia, a1.fldidgrupotallas,
           g.flddescripcion AS descripcion_grupo_tallas,
           p.fldnombrefiscal AS nombre_proveedor
    FROM compras_unpivoted cu
    LEFT JOIN raw.articulo1 a1 ON cu.fldidarticulo = a1.fldidarticulo
    LEFT JOIN raw.grupotalla g ON a1.fldidgrupotallas = g.fldidgrupotallas
    LEFT JOIN raw.proveedores p ON cu.fldidproveedor = p.fldidproveedor
)
SELECT
    fldidempresa,
    fldidalmacen,
    fldidproveedor,
    nombre_proveedor,
    to_date(fldfecha, 'DD/MM/YYYY') AS fecha,
    fldidarticulo,
    fldidcolor,
    talla_pos::int AS talla_pos,
    talla,
    cantidad,
    acumulado,
    fldidmoneda,
    {_num('fldcambio')} AS "fldCambio",
    descripcion_articulo,
    fldtemporada,
    fldidfamilia,
    fldidgrupotallas,
    descripcion_grupo_tallas
FROM compras_mapped
WHERE talla IS NOT NULL AND btrim(talla) <> ''
"""
