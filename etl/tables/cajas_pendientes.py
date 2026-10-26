"""Tabla `public.cajas_pendientes` — espejo directo de la vista SQL Server
dbo.vw_Cajas_Pendientes. Porta bycos_pg_exports/cajas_pendientes.py.
Modo: passthrough (sin transformación): se copia la vista tal cual, deduplicada
por PK, y se sobreescribe.

Como no hay transformación, la tabla destino se crea con LAS MISMAS columnas que
devuelva la vista (igual que hacía el overwrite de Spark), más actualizado_en.
Las columnas exactas se confirman al correr contra el SQL Server real.
"""
from __future__ import annotations

SOURCES = {
    "cajas_pendientes": "SELECT * FROM dbo.vw_Cajas_Pendientes",
}

TARGET = "public.cajas_pendientes"
# PK de la vista (nombres tal cual los devuelve; en raw van en minúscula).
KEYS = ["DispathNote", "NoBulto", "Articulo", "Color", "Talla"]


def load(pg, dry_run: bool) -> None:
    """Crea public.cajas_pendientes con las columnas de la vista + actualizado_en,
    deduplica por PK y sobreescribe."""
    keys_lower = [k.lower() for k in KEYS]
    order = ", ".join(keys_lower)

    with pg.cursor() as c:
        # Columnas reales cargadas en raw (= columnas de la vista, en minúscula).
        c.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='raw' AND table_name='cajas_pendientes' "
            "ORDER BY ordinal_position"
        )
        raw_cols = [r[0] for r in c.fetchall()]
        if not raw_cols:
            raise RuntimeError("raw.cajas_pendientes no tiene columnas (¿falló la extracción?)")

        faltan = [k for k in keys_lower if k not in raw_cols]
        if faltan:
            raise RuntimeError(
                f"La vista no trae las columnas clave {faltan}. "
                f"Columnas disponibles: {raw_cols}"
            )

        dedup = (f"SELECT DISTINCT ON ({order}) * FROM raw.cajas_pendientes "
                 f"ORDER BY {order}")

        if dry_run:
            c.execute(f"SELECT count(*) FROM ({dedup}) q")
            print(f"  [transform] {TARGET}: {c.fetchone()[0]} filas (deduplicadas)")
            print(f"     columnas: {raw_cols}")
            pg.rollback()
            print(f"  [dry-run] NO se escribió {TARGET}")
            return

        # Tabla destino = columnas de la vista (text) + actualizado_en.
        coldefs = ", ".join(f'"{col}" text' for col in raw_cols)
        c.execute(f"CREATE TABLE IF NOT EXISTS {TARGET} ({coldefs}, "
                  f"actualizado_en timestamp without time zone)")
        c.execute(f"TRUNCATE {TARGET}")
        collist = ", ".join(f'"{col}"' for col in raw_cols)
        c.execute(
            f'INSERT INTO {TARGET} ({collist}, actualizado_en) '
            f"SELECT {collist}, now() FROM ({dedup}) q"
        )
        n = c.rowcount
    pg.commit()
    print(f"  [load] {TARGET}: {n} filas (espejo de la vista)")
