# Databricks notebook source
# MAGIC %md
# MAGIC # Conectar SQL Server (Arsys) con Databricks
# MAGIC
# MAGIC Lee una tabla de tu SQL Server alojado en Arsys usando JDBC.
# MAGIC El driver de SQL Server ya viene incluido en el runtime de Databricks:
# MAGIC no hace falta instalar nada.
# MAGIC
# MAGIC **Antes de empezar**, rellena los valores de la celda de configuración.
# MAGIC Para la contraseña, lo ideal es usar un *secret scope* (ver celda opcional
# MAGIC al final) en lugar de escribirla en claro.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuración

# COMMAND ----------

jdbc_hostname = "82.223.100.253"
jdbc_port     = 4313
database      = "TU_BASE_DE_DATOS"   # nombre de la BD en Arsys
user          = "TU_USUARIO"
password      = "TU_PASSWORD"        # mejor desde secretos (ver celda final)
tabla         = "dbo.TU_TABLA"       # p.ej. dbo.Clientes

# encrypt=true + trustServerCertificate=true evita problemas si el servidor
# de Arsys no tiene un certificado TLS válido/firmado por una CA pública.
# Si aun así falla el handshake TLS, prueba a cambiar encrypt a false.
jdbc_url = (
    f"jdbc:sqlserver://{jdbc_hostname}:{jdbc_port}"
    f";databaseName={database};encrypt=true;trustServerCertificate=true"
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Prueba rápida de conectividad (opcional pero recomendada)
# MAGIC
# MAGIC Comprueba que el compute de Databricks alcanza el puerto. Si esto falla,
# MAGIC casi seguro es el firewall/acceso remoto de Arsys limitado a IPs concretas.

# COMMAND ----------

import socket

try:
    with socket.create_connection((jdbc_hostname, jdbc_port), timeout=10):
        print(f"OK: {jdbc_hostname}:{jdbc_port} es alcanzable desde Databricks")
except Exception as e:
    print(f"NO alcanzable: {e}")
    print("Revisa el acceso remoto/firewall de Arsys (abrir a cualquier IP).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leer la tabla
# MAGIC
# MAGIC Usamos el formato `jdbc` genérico con la URL completa porque esa URL
# MAGIC incluye `trustServerCertificate=true`, necesario para el certificado
# MAGIC autofirmado del SQL Server de Arsys. (El formato nativo `sqlserver`
# MAGIC ignora la URL y fuerza la validación del certificado, lo que provoca
# MAGIC el error "PKIX path building failed".)

# COMMAND ----------

df = (
    spark.read
    .format("jdbc")
    .option("url", jdbc_url)      # la URL lleva encrypt=true;trustServerCertificate=true
    .option("dbtable", tabla)
    .option("user", user)
    .option("password", password)
    .load()
)

display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Alternativa: formato nativo sqlserver
# MAGIC Si prefieres el formato `sqlserver`, hay que pasarle explícitamente las
# MAGIC opciones TLS (no las toma de la URL):

# COMMAND ----------

# df = (
#     spark.read
#     .format("sqlserver")
#     .option("host", jdbc_hostname)
#     .option("port", jdbc_port)
#     .option("database", database)
#     .option("user", user)
#     .option("password", password)
#     .option("dbtable", tabla)
#     .option("encrypt", "true")
#     .option("trustServerCertificate", "true")   # <-- imprescindible con Arsys
#     .load()
# )
# display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Guardar como tabla en Databricks (opcional)
# MAGIC Materializa los datos en una tabla Delta para no depender de Arsys en cada consulta.

# COMMAND ----------

# df.write.mode("overwrite").saveAsTable("mi_catalogo.mi_esquema.mi_tabla")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. (Opcional) Guardar la contraseña en un secret scope
# MAGIC Ejecuta esto UNA vez desde la CLI de Databricks en tu PC, no en el notebook:
# MAGIC ```
# MAGIC databricks secrets create-scope arsys
# MAGIC databricks secrets put-secret arsys sqlserver_password
# MAGIC ```
# MAGIC Y luego en el notebook sustituye la línea del password por:
# MAGIC ```python
# MAGIC password = dbutils.secrets.get(scope="arsys", key="sqlserver_password")
# MAGIC ```
