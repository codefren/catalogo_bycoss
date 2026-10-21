FROM python:3.12-slim

WORKDIR /code

# Usuario sin privilegios: la app no corre como root.
RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser
EXPOSE 8000

# 1 solo worker: va sobrado para un catálogo de 250k filas y, sobre todo, el
# rate limit (slowapi) cuenta en memoria del proceso; con N workers el límite
# real sería N veces el configurado.
# --proxy-headers: toma la IP real del cliente de X-Forwarded-For (lo pone Caddy).
# Solo se fía de las IPs de FORWARDED_ALLOW_IPS (variable que uvicorn lee sola);
# sin esto, el rate limit vería siempre la IP de Caddy y todos los clientes
# compartirían el mismo cupo.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
