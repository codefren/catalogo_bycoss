FROM python:3.12-slim

WORKDIR /app

# Usuario sin privilegios: no corre como root.
RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser
EXPOSE 8000

# Sirve el MCP por Streamable HTTP en /mcp (más /healthz). La auth por token
# (MCP_API_KEY) y las credenciales de la API (CATALOGO_*) llegan por entorno.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
