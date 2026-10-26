FROM python:3.12-slim

WORKDIR /app

# pymssql y psycopg2-binary se instalan como wheels (traen FreeTDS/libpq),
# no hacen falta compiladores ni paquetes de sistema.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Ejecuta el ETL y termina. La programación (cron/compose) se añade aparte.
ENTRYPOINT ["python", "etl.py"]
CMD ["sku"]
