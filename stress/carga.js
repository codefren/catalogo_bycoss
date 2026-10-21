// Prueba de carga de la Catálogo API con k6 (https://k6.io).
//
// Cada endpoint es un escenario con tasa constante (RATE peticiones/segundo).
// El rate limit de la API es por IP y POR ENDPOINT (300/minute = 5 req/s), y
// los tres escenarios de /api/skus comparten endpoint: en producción mantén
// RATE <= 1 para no medir el 429 en vez de la API.
//
// Uso (sin instalar nada, con Docker):
//   set -a; . bruno/.env; set +a
//   docker run --rm -i --network host -v "$PWD/stress:/scripts" grafana/k6 run /scripts/carga.js \
//     -e BASE_URL=https://bycos.data4tex.com \
//     -e USERNAME="$CATALOGO_USERNAME" -e PASSWORD="$CATALOGO_PASSWORD" \
//     -e RATE=1 -e DURATION=2m
import http from "k6/http";
import { check, fail } from "k6";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const RATE = Number(__ENV.RATE || 1);
const DURATION = __ENV.DURATION || "2m";
const FECHA_DESDE = __ENV.FECHA_DESDE || "2025-07-01";
const FECHA_HASTA = __ENV.FECHA_HASTA || "2025-07-31";

// nombre del escenario -> función que ejecuta
const ESCENARIOS = [
  "skus_listado",
  "skus_filtros",
  "skus_texto",
  "sku_detalle",
  "ventas_lineas",
  "ventas_cabeceras",
  "ticket_detalle",
  "compras",
  "cajas",
];

export const options = {
  scenarios: Object.fromEntries(
    ESCENARIOS.map((name) => [
      name,
      {
        executor: "constant-arrival-rate",
        exec: name,
        rate: RATE,
        timeUnit: "1s",
        duration: DURATION,
        preAllocatedVUs: Math.max(2, RATE * 2),
        maxVUs: Math.max(10, RATE * 20),
      },
    ])
  ),
  thresholds: Object.assign(
    {
      http_req_failed: ["rate<0.01"],
      http_req_duration: ["p(95)<1000"],
    },
    // Umbrales holgados por escenario: sirven para que el resumen muestre la
    // latencia desglosada de cada endpoint.
    Object.fromEntries(
      ESCENARIOS.map((n) => [`http_req_duration{scenario:${n}}`, ["p(95)<5000"]])
    )
  ),
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

// Login una vez y ejemplos reales para los endpoints de detalle.
export function setup() {
  const login = http.post(`${BASE}/auth/token`, {
    username: __ENV.USERNAME,
    password: __ENV.PASSWORD,
  });
  if (login.status !== 200) fail(`login falló: ${login.status}`);
  const headers = { Authorization: `Bearer ${login.json("access_token")}` };

  const primero = (path) => {
    const r = http.get(`${BASE}${path}`, { headers });
    const items = r.status === 200 ? r.json("items") : [];
    return items && items.length ? items[0] : null;
  };
  const sku = primero("/api/skus?limit=1");
  const ticket = primero(`/api/ventas?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=1`);
  return { headers, sku: sku && sku.sku, ticket };
}

function get(data, path) {
  const r = http.get(`${BASE}${path}`, { headers: data.headers });
  check(r, { "status 200": (res) => res.status === 200 });
  return r;
}

export function skus_listado(d) { get(d, "/api/skus?limit=50"); }
export function skus_filtros(d) { get(d, "/api/skus?con_stock=true&orden=pvp&direccion=desc&limit=100"); }
export function skus_texto(d) { get(d, "/api/skus?q=camis&limit=50"); }
export function sku_detalle(d) {
  if (d.sku) get(d, `/api/skus/${encodeURIComponent(d.sku)}`);
}
export function ventas_lineas(d) {
  get(d, `/api/ventas?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=100`);
}
export function ventas_cabeceras(d) {
  get(d, `/api/ventas/cabeceras?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=100`);
}
export function ticket_detalle(d) {
  const t = d.ticket;
  if (t) get(d, `/api/ventas/ticket/${t.fldIdEmpresa}/${t.fldIdAlmacen}/${t.fldIdCaja}/${t.fldIdTicket}`);
}
export function compras(d) {
  get(d, `/api/compras?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=100`);
}
export function cajas(d) { get(d, "/api/cajas-pendientes?limit=100"); }
