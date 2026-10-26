"""Tabla `public.ticket_maestro` — una fila por linea de ticket (cabecera+linea).
Porta bycos_pg_exports/ticket_maestro.py. Modo: INCREMENTAL (append-only).

Son ~1.7M filas y crecen; no se reescribe entera. Se lee solo la ventana
reciente de SQL Server, se deduplica por PK de linea y se insertan (append)
solo las que no existen ya en Postgres (anti-join por la ventana). Limitacion:
lineas viejas corregidas/anuladas no se propagan (haría falta reconciliación).
"""
from __future__ import annotations

from common import ACTUALIZADO_EN

JDBC_DAYS = 5      # margen de lectura en SQL Server
WINDOW_DAYS = 3    # ventana que se entrega al load
ANTIJOIN_DAYS = 4  # margen del anti-duplicados en Postgres

_CAB_COLS = [
    "fldIdEmpresa", "fldIdAlmacen", "fldIdCaja", "fldIdTicket", "fldFecha",
    "fldHora", "fldIdCliente", "fldIdOperario", "fldIdCajera", "fldPrendas",
    "fldImporteBruto", "fldImporteDto", "fldImporteNeto", "fldCobradoTicket",
    "fldPteTicket", "fldIdMoneda", "fldCambio", "fldDto", "fldIdCierre",
    "fldVales", "fldApartados", "fldArreglos", "fldPromociones",
    "fldChequeRegalo", "fldCupones", "fldEspecial", "fldIdVale",
]
_LIN_COLS = [
    "fldIdEmpresa", "fldIdAlmacen", "fldIdCaja", "fldIdTicket", "fldLinea",
    "fldIdArticulo", "fldIdColor", "fldTalla", "fldCantidad", "fldPrecio",
    "fldDto", "fldImporte", "fldIdPromocion", "fldIdPromoCat", "fldIVA",
    "fldVentaReal", "fldIdRebaja",
]

_CAB_WHERE = f"CONVERT(date, fldFecha, 103) >= DATEADD(day, -{JDBC_DAYS}, GETDATE())"
SOURCES = {
    "ticket_cabecera": (
        f"SELECT {', '.join(_CAB_COLS)} FROM dbo.tbdTicketCabecera WHERE {_CAB_WHERE}"
    ),
    "ticket_linea": (
        f"SELECT {', '.join('l.' + c for c in _LIN_COLS)} FROM dbo.tbdTicketLineas l "
        f"WHERE EXISTS (SELECT 1 FROM dbo.tbdTicketCabecera c "
        f"  WHERE CONVERT(date, c.fldFecha, 103) >= DATEADD(day, -{JDBC_DAYS}, GETDATE()) "
        f"  AND c.fldIdEmpresa = l.fldIdEmpresa AND c.fldIdAlmacen = l.fldIdAlmacen "
        f"  AND c.fldIdCaja = l.fldIdCaja AND c.fldIdTicket = l.fldIdTicket)"
    ),
}

TARGET = "public.ticket_maestro"
TARGET_DDL = """
CREATE TABLE IF NOT EXISTS public.ticket_maestro (
    "fldIdEmpresa" text, "fldIdAlmacen" text, "fldIdCaja" text,
    "fldIdTicket" text, "fldLinea" text, fecha date, "fldHora" text,
    "fldIdCliente" text, "fldIdOperario" text, "fldIdCajera" text,
    "fldPrendas" double precision, "fldImporteBruto" double precision,
    "fldImporteDto" double precision, "fldImporteNeto" double precision,
    "fldCobradoTicket" double precision, "fldPteTicket" double precision,
    "fldIdMoneda" text, "fldCambio" double precision,
    dto_cabecera double precision, id_cierre text,
    "fldVales" double precision, "fldApartados" double precision,
    "fldArreglos" double precision, "fldPromociones" double precision,
    "fldChequeRegalo" double precision, "fldCupones" double precision,
    "fldEspecial" double precision, "fldIdVale" text,
    "fldIdArticulo" text, "fldIdColor" text, "fldTalla" text, sku text,
    "fldCantidad" double precision, "fldPrecio" double precision,
    dto_linea double precision, importe_linea double precision,
    "fldIdPromocion" text, "fldIdPromoCat" text, "fldIVA" double precision,
    "fldVentaReal" double precision, "fldIdRebaja" text,
    actualizado_en timestamp without time zone NOT NULL
)
"""
TARGET_COLUMNS = [
    "fldIdEmpresa", "fldIdAlmacen", "fldIdCaja", "fldIdTicket", "fldLinea",
    "fecha", "fldHora", "fldIdCliente", "fldIdOperario", "fldIdCajera",
    "fldPrendas", "fldImporteBruto", "fldImporteDto", "fldImporteNeto",
    "fldCobradoTicket", "fldPteTicket", "fldIdMoneda", "fldCambio",
    "dto_cabecera", "id_cierre", "fldVales", "fldApartados", "fldArreglos",
    "fldPromociones", "fldChequeRegalo", "fldCupones", "fldEspecial",
    "fldIdVale", "fldIdArticulo", "fldIdColor", "fldTalla", "sku",
    "fldCantidad", "fldPrecio", "dto_linea", "importe_linea", "fldIdPromocion",
    "fldIdPromoCat", "fldIVA", "fldVentaReal", "fldIdRebaja",
]
# PK de linea: (columna destino, columna del SELECT en minuscula)
PK_MAP = [
    ("fldIdEmpresa", "fldidempresa"), ("fldIdAlmacen", "fldidalmacen"),
    ("fldIdCaja", "fldidcaja"), ("fldIdTicket", "fldidticket"),
    ("fldLinea", "fldlinea"),
]


def _num(col: str) -> str:
    return f"NULLIF(btrim({col}), '')::numeric"


def build_select() -> str:
    return f"""
SELECT
    l.fldidempresa, l.fldidalmacen, l.fldidcaja, l.fldidticket, l.fldlinea,
    to_date(c.fldfecha, 'DD/MM/YYYY') AS fecha,
    c.fldhora, c.fldidcliente, c.fldidoperario, c.fldidcajera,
    {_num('c.fldprendas')} AS "fldPrendas",
    {_num('c.fldimportebruto')} AS "fldImporteBruto",
    {_num('c.fldimportedto')} AS "fldImporteDto",
    {_num('c.fldimporteneto')} AS "fldImporteNeto",
    {_num('c.fldcobradoticket')} AS "fldCobradoTicket",
    {_num('c.fldpteticket')} AS "fldPteTicket",
    c.fldidmoneda,
    {_num('c.fldcambio')} AS "fldCambio",
    {_num('c.flddto')} AS dto_cabecera,
    c.fldidcierre AS id_cierre,
    {_num('c.fldvales')} AS "fldVales",
    {_num('c.fldapartados')} AS "fldApartados",
    {_num('c.fldarreglos')} AS "fldArreglos",
    {_num('c.fldpromociones')} AS "fldPromociones",
    {_num('c.fldchequeregalo')} AS "fldChequeRegalo",
    {_num('c.fldcupones')} AS "fldCupones",
    {_num('c.fldespecial')} AS "fldEspecial",
    c.fldidvale,
    l.fldidarticulo, l.fldidcolor, l.fldtalla,
    CONCAT_WS('-', l.fldidarticulo, l.fldidcolor, l.fldtalla) AS sku,
    {_num('l.fldcantidad')} AS "fldCantidad",
    {_num('l.fldprecio')} AS "fldPrecio",
    {_num('l.flddto')} AS dto_linea,
    {_num('l.fldimporte')} AS importe_linea,
    l.fldidpromocion, l.fldidpromocat,
    {_num('l.fldiva')} AS "fldIVA",
    {_num('l.fldventareal')} AS "fldVentaReal",
    l.fldidrebaja
FROM raw.ticket_linea l
LEFT JOIN raw.ticket_cabecera c
  ON  l.fldidempresa = c.fldidempresa
  AND l.fldidalmacen = c.fldidalmacen
  AND l.fldidcaja    = c.fldidcaja
  AND l.fldidticket  = c.fldidticket
WHERE to_date(c.fldfecha, 'DD/MM/YYYY') >= current_date - {WINDOW_DAYS}
"""


def load(pg, dry_run: bool) -> None:
    """Carga incremental: dedup por PK + anti-join contra la ventana en PG."""
    with pg.cursor() as c:
        c.execute(TARGET_DDL)
    pg.commit()

    pk_stage = ", ".join(s for _, s in PK_MAP)
    inner = f"SELECT DISTINCT ON ({pk_stage}) * FROM ({build_select()}) s ORDER BY {pk_stage}"
    antijoin = " AND ".join(f't."{t}" = q.{s}' for t, s in PK_MAP)
    where_new = (
        f"NOT EXISTS (SELECT 1 FROM {TARGET} t WHERE {antijoin} "
        f"AND t.\"fecha\" >= current_date - {ANTIJOIN_DAYS})"
    )
    cols = ", ".join(f'"{col}"' for col in TARGET_COLUMNS)

    with pg.cursor() as c:
        if dry_run:
            c.execute(f"SELECT count(*) FROM ({inner}) q WHERE {where_new}")
            print(f"  [transform] {TARGET}: {c.fetchone()[0]} lineas NUEVAS (incremental)")
            c.execute(f"SELECT sku, fecha, \"fldCantidad\", importe_linea "
                      f"FROM ({inner}) q WHERE {where_new} LIMIT 3")
            for row in c.fetchall():
                print("     muestra:", row)
            pg.rollback()
            print(f"  [dry-run] NO se escribió {TARGET}")
            return
        c.execute(
            f'INSERT INTO {TARGET} ({cols}, "actualizado_en") '
            f"SELECT *, {ACTUALIZADO_EN} FROM ({inner}) q WHERE {where_new}"
        )
        n = c.rowcount
    pg.commit()
    print(f"  [load] {TARGET}: +{n} lineas nuevas (append incremental)")
