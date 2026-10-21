# Pruebas de carga (k6)

- `carga.js` — escenarios k6, uno por endpoint, a tasa constante (`RATE` req/s cada uno).
- `datos_sinteticos.sql` — tablas y datos falsos para probar **en local** (sku 250k,
  ticket_maestro 500k, compras 100k, cajas 20k).
- `indices.sql` — índices recomendados (`CREATE INDEX CONCURRENTLY`, seguro en prod).

## Producción (carga suave)

El rate limit es 300/min por IP y endpoint, y los 3 escenarios de `/api/skus` comparten
endpoint: usa `RATE=1` como máximo.

```bash
set -a; . bruno/.env; set +a
docker run --rm -i -v "$PWD/stress:/scripts" grafana/k6 run /scripts/carga.js \
  -e BASE_URL=https://bycos.data4tex.com \
  -e USERNAME="$CATALOGO_USERNAME" -e PASSWORD="$CATALOGO_PASSWORD" \
  -e RATE=1 -e DURATION=2m
```

## Local (capacidad)

```bash
docker network create cat-test-net
docker run -d --rm --name cat-test-pg --network cat-test-net --cpus=2 --memory=2g \
  -e POSTGRES_PASSWORD=pw -e POSTGRES_USER=catalogo -e POSTGRES_DB=catalogo \
  postgres:16-alpine postgres -c shared_buffers=256MB -c work_mem=16MB
docker exec -i cat-test-pg psql -U catalogo -d catalogo < stress/datos_sinteticos.sql
docker build -t catalogo-api-test ./api
docker run -d --rm --name cat-test-api --network cat-test-net --cpus=1 -p 127.0.0.1:18080:8000 \
  -e DATABASE_URL=postgresql+asyncpg://catalogo:pw@cat-test-pg:5432/catalogo \
  -e JWT_SECRET=test -e RATE_LIMIT=100000/minute catalogo-api-test
docker exec cat-test-api python create_user.py tester secreto

docker run --rm -i --network host -v "$PWD/stress:/scripts" grafana/k6 run /scripts/carga.js \
  -e BASE_URL=http://127.0.0.1:18080 -e USERNAME=tester -e PASSWORD=secreto -e RATE=5 -e DURATION=1m

# Con índices:
docker exec -i cat-test-pg psql -U catalogo -d catalogo < stress/indices.sql
```

## Resultados (2026-10-21)

| Entorno | Carga | p95 | Errores |
|---|---|---|---|
| Producción, estado actual | ~6 req/s (9 objetivo) | **36 s** | **26 %** |
| Producción con índices | 9 req/s | 296 ms | 23 % (todo `429` en `/api/skus`; resto 0 %) |
| Producción con índices y `RATE_LIMIT=300/minute` | 9 req/s | 417 ms | 0 % |
| Local sin índices | 9 req/s | 455 ms | 0 % |
| Local sin índices | 27 req/s objetivo (alcanzó 16) | 20 s | 0 % (iteraciones descartadas) |
| Local con índices | 9 req/s | 54 ms | 0 % |
| Local con índices | 45 req/s | 55 ms | 0 % |
| Local con índices | 90 req/s | 57 ms | 0 % |
| Local con índices | 180 req/s objetivo (alcanzó 134) | 16 s | 53 % (CPU de la API saturada) |

Local: Postgres 2 CPU / 2 GB, API 1 worker / 1 CPU, datos sintéticos.
