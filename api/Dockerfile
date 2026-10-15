FROM python:3.12-slim

WORKDIR /code

# Usuario sin privilegios: la app no corre como root.
RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser
EXPOSE 8000

# 2 workers van sobrados para un catálogo de 250k filas.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
