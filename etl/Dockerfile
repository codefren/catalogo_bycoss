FROM python:3.12-slim

WORKDIR /app

# supercronic: cron para contenedores (lee una crontab y loguea a stdout, sin
# root). tzdata: para que la crontab use la zona horaria local (TZ).
ADD https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic \
    && apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# pymssql y psycopg2-binary se instalan como wheels (traen FreeTDS/libpq),
# no hacen falta compiladores ni paquetes de sistema.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Por defecto ejecuta el ETL una vez (uso manual / docker compose run).
# El servicio etl-cron sobreescribe el entrypoint para correr supercronic.
ENTRYPOINT ["python", "etl.py"]
CMD ["sku"]
