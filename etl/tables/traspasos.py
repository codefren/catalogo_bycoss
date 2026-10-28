"""Tabla `public.traspasos` — traspasos (movimientos entre almacenes) a nivel de
línea-talla. Origen: SQL Server tbdTraspasos (cabecera) + tbdTraspasosLineas
(líneas, anchas por talla).

Modo: INCREMENTAL por día. Por defecto solo procesa el día actual (TRASPASOS_DIAS=0):
borra en Postgres las filas de la ventana [hoy - DIAS, hoy] y reinserta las de
esa ventana, sin tocar el histórico. Así capta ediciones del mismo día y es muy
ligero. Para cargar el histórico una vez, ejecutar con TRASPASOS_DIAS alto.

Solo traspasos con origen Y destino entre 00000001 y 00000220 (entre tiendas).
Las líneas se expanden (unpivot de fldTalla1-15) a una fila por talla con
cantidad != 0; la talla se mapea con el grupo de tallas del artículo. Se añade
la descripción del almacén de origen y de destino.

La API agrupa estas filas por traspaso para devolver el JSON anidado
(cabecera + lineas).
"""
from __future__ import annotations

import os

from common import ACTUALIZADO_EN

RNG = range(1, 16)

# Rango de almacenes (tiendas) para origen y destino.
ALM_MIN = "00000001"
ALM_MAX = "00000220"

# Ventana incremental: nº de días hacia atrás desde HOY que se procesan.
#   0 (por defecto) = solo el día actual (actualización incremental diaria).
#   Para un backfill histórico, ejecutar una vez con TRASPASOS_DIAS alto:
#     docker compose run --rm -e TRASPASOS_DIAS=9999 etl traspasos
DIAS = int(os.getenv("TRASPASOS_DIAS", "0"))


def _filtro(alias: str = "") -> str:
    """Filtro SQL Server: rango de almacenes (origen/destino) + ventana de días."""
    p = f"{alias}." if alias else ""
    return (
        f"{p}fldIdOrigen BETWEEN '{ALM_MIN}' AND '{ALM_MAX}' "
        f"AND {p}fldIdDestino BETWEEN '{ALM_MIN}' AND '{ALM_MAX}' "
        f"AND CONVERT(date, {p}fldFecha, 103) >= DATEADD(day, -{DIAS}, CAST(GETDATE() AS date))"
    )


_LINEAS_COLS = (
    ["fldIdTraspaso", "fldLinea", "fldIdArticulo", "fldIdColor"]
    + [f"fldTalla{i}" for i in RNG]
)
_GT_COLS = ["fldIdGrupoTallas"] + [f"fldTalla{i}" for i in RNG]

SOURCES = {
    "traspasos": (
        "SELECT fldIdTraspaso, fldIdOrigen, fldIdDestino, fldFecha, fldTipo "
        f"FROM dbo.tbdTraspasos WHERE {_filtro()}"
    ),
    "traspasos_lineas": (
        f"SELECT {', '.join('l.' + c for c in _LINEAS_COLS)} "
        "FROM dbo.tbdTraspasosLineas l WHERE EXISTS ("
        "SELECT 1 FROM dbo.tbdTraspasos t "
        f"WHERE t.fldIdTraspaso = l.fldIdTraspaso AND {_filtro('t')})"
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


def load(pg, dry_run: bool) -> None:
    """Carga incremental por día: borra la ventana [hoy-DIAS, hoy] en Postgres y
    reinserta las filas de esa ventana (el histórico fuera de la ventana no se
    toca). Con DIAS=0 (por defecto) solo refresca el día actual."""
    with pg.cursor() as c:
        c.execute(TARGET_DDL)
    pg.commit()

    select_sql = build_select()
    cols = ", ".join(f'"{col}"' for col in TARGET_COLUMNS)
    desde = f"(now() AT TIME ZONE 'Europe/Madrid')::date - {DIAS}"

    with pg.cursor() as c:
        if dry_run:
            c.execute(f"SELECT count(*) FROM ({select_sql}) q")
            print(f"  [transform] {TARGET}: {c.fetchone()[0]} filas (ventana {DIAS}d desde hoy)")
            c.execute(f'SELECT "fldIdTraspaso", fecha, sku, cantidad '
                      f"FROM ({select_sql}) q LIMIT 3")
            for row in c.fetchall():
                print("     muestra:", row)
            pg.rollback()
            print(f"  [dry-run] NO se escribió {TARGET}")
            return

        c.execute(f"DELETE FROM {TARGET} WHERE fecha >= {desde}")
        borradas = c.rowcount
        c.execute(
            f'INSERT INTO {TARGET} ({cols}, "actualizado_en") '
            f"SELECT *, {ACTUALIZADO_EN} FROM ({select_sql}) q"
        )
        insertadas = c.rowcount
    pg.commit()
    print(f"  [load] {TARGET}: -{borradas} +{insertadas} (ventana {DIAS}d desde hoy)")
