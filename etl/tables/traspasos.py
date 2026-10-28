"""Tabla `public.traspasos` — traspasos (movimientos entre almacenes) a nivel de
línea-talla. Origen: SQL Server tbdTraspasos (cabecera) + tbdTraspasosLineas
(líneas, anchas por talla). Modo: overwrite.

Solo traspasos con origen Y destino entre 00000001 y 00000220 (entre tiendas).
Las líneas se expanden (unpivot de fldTalla1-15) a una fila por talla con
cantidad != 0; la talla se mapea con el grupo de tallas del artículo. Se añade
la descripción del almacén de origen y de destino.

La API agrupa estas filas por traspaso para devolver el JSON anidado
(cabecera + lineas).
"""
from __future__ import annotations

RNG = range(1, 16)

# Rango de almacenes (tiendas) para origen y destino.
ALM_MIN = "00000001"
ALM_MAX = "00000220"

def _rango(alias: str = "") -> str:
    """Filtro de rango de almacenes para origen y destino (con alias opcional)."""
    p = f"{alias}." if alias else ""
    return (
        f"{p}fldIdOrigen BETWEEN '{ALM_MIN}' AND '{ALM_MAX}' "
        f"AND {p}fldIdDestino BETWEEN '{ALM_MIN}' AND '{ALM_MAX}'"
    )


_LINEAS_COLS = (
    ["fldIdTraspaso", "fldLinea", "fldIdArticulo", "fldIdColor"]
    + [f"fldTalla{i}" for i in RNG]
)
_GT_COLS = ["fldIdGrupoTallas"] + [f"fldTalla{i}" for i in RNG]

SOURCES = {
    "traspasos": (
        "SELECT fldIdTraspaso, fldIdOrigen, fldIdDestino, fldFecha, fldTipo "
        f"FROM dbo.tbdTraspasos WHERE {_rango()}"
    ),
    "traspasos_lineas": (
        f"SELECT {', '.join('l.' + c for c in _LINEAS_COLS)} "
        "FROM dbo.tbdTraspasosLineas l WHERE EXISTS ("
        "SELECT 1 FROM dbo.tbdTraspasos t "
        f"WHERE t.fldIdTraspaso = l.fldIdTraspaso AND {_rango('t')})"
    ),
    "articulo1": "SELECT fldIdArticulo, fldIdGrupoTallas FROM dbo.tbdArticulos0",
    "grupotalla": f"SELECT {', '.join(_GT_COLS)} FROM dbo.tbdGruposTallas",
    "almacenes": "SELECT fldIdAlmacen, fldDescripcion FROM dbo.tbdAlmacenes",
}

TARGET = "public.traspasos"
TARGET_DDL = """
CREATE TABLE IF NOT EXISTS public.traspasos (
    "fldIdTraspaso" text,
    "fldIdOrigen" text,
    origen_descripcion text,
    "fldIdDestino" text,
    destino_descripcion text,
    fecha date,
    "fldTipo" text,
    "fldLinea" text,
    "fldIdArticulo" text,
    "fldIdColor" text,
    talla text,
    sku text,
    cantidad double precision,
    actualizado_en timestamp without time zone NOT NULL
)
"""
TARGET_COLUMNS = [
    "fldIdTraspaso", "fldIdOrigen", "origen_descripcion", "fldIdDestino",
    "destino_descripcion", "fecha", "fldTipo", "fldLinea", "fldIdArticulo",
    "fldIdColor", "talla", "sku", "cantidad",
]
KEYS = ["fldIdTraspaso", "fldLinea", "talla"]


def _num(col: str) -> str:
    return f"NULLIF(btrim({col}), '')::numeric"


def build_select() -> str:
    lineas_values = ",\n            ".join(
        f"({i}, {_num(f'fldtalla{i}')})" for i in RNG
    )
    talla_case = "CASE lu.talla_pos " + " ".join(
        f"WHEN {i} THEN g.fldtalla{i}" for i in RNG
    ) + " END"
    return f"""
WITH lineas_unpiv AS (
    SELECT l.fldidtraspaso, l.fldlinea, l.fldidarticulo, l.fldidcolor,
           u.talla_pos, u.cantidad
    FROM raw.traspasos_lineas l
    CROSS JOIN LATERAL (VALUES
            {lineas_values}
    ) AS u(talla_pos, cantidad)
    WHERE u.cantidad <> 0
),
mapped AS (
    SELECT lu.fldidtraspaso, lu.fldlinea, lu.fldidarticulo, lu.fldidcolor,
           {talla_case} AS talla,
           lu.cantidad
    FROM lineas_unpiv lu
    JOIN raw.articulo1 a ON lu.fldidarticulo = a.fldidarticulo
    JOIN raw.grupotalla g ON a.fldidgrupotallas = g.fldidgrupotallas
)
SELECT
    t.fldidtraspaso,
    t.fldidorigen,
    ao.flddescripcion AS origen_descripcion,
    t.fldiddestino,
    ad.flddescripcion AS destino_descripcion,
    to_date(t.fldfecha, 'DD/MM/YYYY') AS fecha,
    t.fldtipo,
    m.fldlinea,
    m.fldidarticulo,
    m.fldidcolor,
    m.talla,
    CONCAT_WS('-', m.fldidarticulo, m.fldidcolor, m.talla) AS sku,
    m.cantidad
FROM mapped m
JOIN raw.traspasos t ON m.fldidtraspaso = t.fldidtraspaso
LEFT JOIN raw.almacenes ao ON t.fldidorigen = ao.fldidalmacen
LEFT JOIN raw.almacenes ad ON t.fldiddestino = ad.fldidalmacen
WHERE m.talla IS NOT NULL AND btrim(m.talla) <> ''
"""
