# Databricks notebook source
# MAGIC %md
# MAGIC # Sincronizar tabla SQL Server (Arsys) -> Delta en Databricks
# MAGIC
# MAGIC Mantiene una copia Delta de la tabla y la actualiza con MERGE (upsert):
# MAGIC actualiza filas cambiadas, inserta nuevas y (modo A) borra las eliminadas.
# MAGIC
# MAGIC - **Modo A (snapshot + merge):** lee toda la tabla cada vez. Solo necesita clave primaria.
# MAGIC - **Modo B (incremental):** lee solo lo cambiado. Necesita clave primaria + columna de fecha.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuración

# COMMAND ----------

jdbc_hostname = "82.223.100.253"
jdbc_port     = 4313
database      = "TU_BASE_DE_DATOS"
user          = "TU_USUARIO"
password      = "TU_PASSWORD"          # mejor usar dbutils.secrets.get(...)

origen_tabla  = "dbo.TU_TABLA"          # tabla de origen en Arsys
destino_tabla = "workspace.default.mi_tabla"   # tabla Delta destino en Databricks
clave         = ["fldidalmacen", "fldidarticulo"]   # clave primaria compuesta

# Esta tabla no tiene columna de fecha -> usamos el modo A (celda 3A).
col_modificacion = None

jdbc_url = (
    f"jdbc:sqlserver://{jdbc_hostname}:{jdbc_port}"
    f";databaseName={database};encrypt=true;trustServerCertificate=true"
)

# Normaliza la clave a lista
claves = clave if isinstance(clave, list) else [clave]

def leer_jdbc(dbtable):
    return (
        spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", dbtable)
        .option("user", user)
        .option("password", password)
        .load()
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Carga inicial (ejecútala UNA vez)
# MAGIC Crea la tabla Delta destino con todo el contenido actual.

# COMMAND ----------

df_full = leer_jdbc(origen_tabla)
df_full.write.mode("overwrite").saveAsTable(destino_tabla)
print(f"Carga inicial OK: {df_full.count()} filas en {destino_tabla}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3A. MODO A — Snapshot completo + MERGE
# MAGIC Lee toda la tabla y la fusiona por clave. Detecta cambios, altas y bajas.
# MAGIC Ejecuta esta celda cada vez que quieras sincronizar.

# COMMAND ----------

# Permite que, si el origen gana columnas nuevas, se añadan solas al destino
# (en vez de fallar por desajuste de esquema).
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")

origen = leer_jdbc(origen_tabla)
origen.createOrReplaceTempView("origen")

cond = " AND ".join([f"t.`{k}` = s.`{k}`" for k in claves])

spark.sql(f"""
MERGE INTO {destino_tabla} t
USING origen s
ON {cond}
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
""")

print("Sincronización (modo A) completada")
display(spark.sql(f"SELECT COUNT(*) AS filas FROM {destino_tabla}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3B. MODO B — Incremental (solo filas cambiadas)
# MAGIC Requiere `col_modificacion`. Lee solo lo que cambió desde la última sync.
# MAGIC No detecta borrados. Usa esta celda en lugar de la 3A si tienes columna de fecha.

# COMMAND ----------

if col_modificacion:
    # Última fecha que ya tenemos en el destino
    ultima = spark.sql(
        f"SELECT MAX(`{col_modificacion}`) AS m FROM {destino_tabla}"
    ).collect()[0]["m"]
    print(f"Última fecha sincronizada: {ultima}")

    if ultima is None:
        filtro = origen_tabla
    else:
        # Pushdown: el filtro se ejecuta en SQL Server, no en Databricks
        filtro = (
            f"(SELECT * FROM {origen_tabla} "
            f"WHERE [{col_modificacion}] > '{ultima}') AS q"
        )

    cambios = leer_jdbc(filtro)
    n = cambios.count()
    print(f"Filas nuevas/modificadas: {n}")

    if n > 0:
        spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        cambios.createOrReplaceTempView("cambios")
        cond = " AND ".join([f"t.`{k}` = s.`{k}`" for k in claves])
        spark.sql(f"""
        MERGE INTO {destino_tabla} t
        USING cambios s
        ON {cond}
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """)
        print("Sincronización (modo B) completada")
else:
    print("col_modificacion no definida: usa el modo A (celda 3A).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Consultar la copia Delta

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {destino_tabla} LIMIT 100"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Automatizar (opcional)
# MAGIC Para que se ejecute solo: crea un **Job / Workflow** en Databricks
# MAGIC (menú Jobs), apunta a este notebook y ponle un horario (p.ej. cada hora).
# MAGIC Quita de este notebook la celda de carga inicial (2) para que el job
# MAGIC solo ejecute la sincronización (3A o 3B).
