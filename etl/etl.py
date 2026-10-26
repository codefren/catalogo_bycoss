"""ETL SQL Server (Arsys) -> PostgreSQL (catálogo que sirve la API).

Reemplaza el pipeline de Databricks: por cada tabla, extrae las fuentes de SQL
Server al esquema `raw`, aplica la transformación en SQL de Postgres y carga la
tabla final `public.*`. Sin Spark, sin Databricks.

Uso:
    python etl.py sku --dry-run    # calcula y muestra, NO escribe
    python etl.py sku              # carga public.sku de verdad
    python etl.py                  # todas las tablas registradas
"""
from __future__ import annotations

import argparse
import sys
import time

from db import mssql_conn, pg_conn
from extract import extract
from tables import (
    cajas_pendientes,
    compras_maestro,
    sku,
    stock,
    stock_talla,
    ticket_maestro,
)

# Registro de tablas (orden de ejecución por defecto).
TABLES = {
    "sku": sku,
    "stock": stock,
    "stock_talla": stock_talla,
    "compras_maestro": compras_maestro,
    "ticket_maestro": ticket_maestro,
    "cajas_pendientes": cajas_pendientes,
}


def run_table(mod, dry_run: bool) -> None:
    t0 = time.time()
    ms = mssql_conn()
    pg = pg_conn()
    try:
        # 1. Extracción de fuentes -> raw.*
        # Los passthrough conservan el case original de las columnas (PRESERVE_CASE).
        lower_case = not getattr(mod, "PRESERVE_CASE", False)
        for raw_name, source_sql in mod.SOURCES.items():
            n = extract(ms, pg, raw_name, source_sql, lower_case=lower_case)
            print(f"  [extract] raw.{raw_name}: {n} filas")

        # 2a. Módulos con carga propia (incremental / passthrough): delegar.
        if hasattr(mod, "load"):
            mod.load(pg, dry_run)
            print(f"  [ok] {mod.TARGET} ({time.time()-t0:.1f}s)")
            return

        # 2b. Overwrite genérico (tabla destino, no-op si ya existe)
        with pg.cursor() as c:
            c.execute(mod.TARGET_DDL)
        pg.commit()

        select_sql = mod.build_select()
        cols = ", ".join(f'"{c}"' for c in mod.TARGET_COLUMNS)

        if dry_run:
            with pg.cursor() as c:
                c.execute(f"SELECT count(*) FROM ({select_sql}) q")
                print(f"  [transform] {mod.TARGET}: {c.fetchone()[0]} filas calculadas")
                c.execute(f"SELECT * FROM ({select_sql}) q LIMIT 3")
                for row in c.fetchall():
                    print("     muestra:", row)
            pg.rollback()
            print(f"  [dry-run] NO se escribió {mod.TARGET} ({time.time()-t0:.1f}s)")
            return

        # 3. Carga transaccional: TRUNCATE + INSERT (la API ve datos consistentes)
        with pg.cursor() as c:
            c.execute(f"TRUNCATE {mod.TARGET}")
            c.execute(
                f'INSERT INTO {mod.TARGET} ({cols}, "actualizado_en") '
                f"SELECT *, now() FROM ({select_sql}) q"
            )
            n = c.rowcount
        pg.commit()
        print(f"  [load] {mod.TARGET}: {n} filas ({time.time()-t0:.1f}s)")
    except Exception:
        pg.rollback()
        raise
    finally:
        ms.close()
        pg.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="ETL SQL Server -> Postgres (catálogo)")
    ap.add_argument("tablas", nargs="*", help="tablas a procesar (por defecto: todas)")
    ap.add_argument("--dry-run", action="store_true",
                    help="calcula y muestra una muestra, sin escribir en Postgres")
    ap.add_argument("--loop", action="store_true",
                    help="ejecuta en bucle cada --interval segundos (para el contenedor)")
    ap.add_argument("--interval", type=int, default=3600,
                    help="segundos entre ejecuciones en modo --loop (por defecto 3600)")
    args = ap.parse_args()

    objetivos = args.tablas or list(TABLES)
    desconocidas = [t for t in objetivos if t not in TABLES]
    if desconocidas:
        print(f"Tablas desconocidas: {', '.join(desconocidas)}. "
              f"Disponibles: {', '.join(TABLES)}", file=sys.stderr)
        sys.exit(2)

    def una_pasada() -> None:
        for t in objetivos:
            print(f"=== {t} ===", flush=True)
            try:
                run_table(TABLES[t], args.dry_run)
            except Exception as e:  # noqa: BLE001 — un fallo de una tabla no tumba el resto
                print(f"[error] {t}: {e}", file=sys.stderr, flush=True)

    if not args.loop:
        una_pasada()
        return

    # Modo bucle: ejecuta, duerme, repite. Pensado para correr en el contenedor.
    while True:
        una_pasada()
        print(f"[loop] durmiendo {args.interval}s", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
