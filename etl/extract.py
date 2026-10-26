"""Extracción genérica: una consulta de SQL Server -> tabla en el esquema `raw`
de PostgreSQL.

Estrategia simple y robusta:
  - Lee la consulta en SQL Server.
  - Crea raw.<nombre> con TODAS las columnas como `text` (los nombres se pasan a
    minúsculas para evitar líos de mayúsculas entre SQL Server y Postgres).
  - Carga por lotes con COPY (rápido). Las cadenas vacías se guardan como NULL.

Las transformaciones (que castean a numérico lo que haga falta) van después, en
SQL de Postgres sobre estas tablas `raw`.
"""
from __future__ import annotations

import csv
import io

BATCH = 50_000


def extract(mssql, pg, raw_name: str, source_sql: str, lower_case: bool = True) -> int:
    """Copia el resultado de `source_sql` (SQL Server) a raw.<raw_name> (Postgres).

    Por defecto pasa los nombres de columna a minúscula (las transformaciones los
    referencian así). `lower_case=False` conserva el case original: necesario para
    los passthrough (p. ej. cajas_pendientes), donde la tabla destino debe tener
    los mismos nombres que la vista para que la API los encuentre.

    Devuelve el número de filas cargadas.
    """
    cur = mssql.cursor()
    cur.execute(source_sql)
    cols = [(d[0].lower() if lower_case else d[0]) for d in cur.description]

    with pg.cursor() as pcur:
        pcur.execute("CREATE SCHEMA IF NOT EXISTS raw")
        pcur.execute(f'DROP TABLE IF EXISTS raw."{raw_name}"')
        coldefs = ", ".join(f'"{c}" text' for c in cols)
        pcur.execute(f'CREATE TABLE raw."{raw_name}" ({coldefs})')
    pg.commit()

    copy_sql = (
        f'COPY raw."{raw_name}" FROM STDIN WITH (FORMAT csv, NULL \'\')'
    )
    total = 0
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        for r in rows:
            writer.writerow(["" if v is None else str(v) for v in r])
        buf.seek(0)
        with pg.cursor() as pcur:
            pcur.copy_expert(copy_sql, buf)
        pg.commit()
        total += len(rows)
    cur.close()
    return total
