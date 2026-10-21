// Prueba de pico: rampa escalonada que se DETIENE SOLA al degradarse.
//
// Un escenario por endpoint distinto (el rate limit es por IP y por endpoint).
// Cada escalón dura ESCALON segundos; la tasa por endpoint sube de PASO en PASO
// hasta MAX. Con el rate limit de producción (300/min = 5 req/s por endpoint)
// MAX debe quedarse por debajo de 5; por encima solo se mediría el 429.
//
// Corta la prueba (abortOnFail) si los errores reales (no 200 ni 429) superan
// el 5 % o el p95 pasa de 3 s. Cada petición se etiqueta con su escalón
// (`etapa`) para ver en el resumen dónde empezó a degradarse.
//
//   set -a; . bruno/.env; set +a
//   docker run --rm -i -v "$PWD/stress:/scripts" grafana/k6 run /scripts/pico.js \
//     -e BASE_URL=https://bycos.data4tex.com \
//     -e USERNAME="$CATALOGO_USERNAME" -e PASSWORD="$CATALOGO_PASSWORD"
import http from "k6/http";
import exec from "k6/execution";
import { fail } from "k6";
import { Counter, Rate } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const PASO = Number(__ENV.PASO || 0.5);
const MAX = Number(__ENV.MAX || 4.5);
const ESCALON = Number(__ENV.ESCALON || 30);
const FECHA_DESDE = __ENV.FECHA_DESDE || "2025-07-01";
const FECHA_HASTA = __ENV.FECHA_HASTA || "2025-07-31";

const errores = new Rate("errores_reales");      // ni 200 ni 429
const limitadas = new Counter("limitadas_429");

const ESCENARIOS = [
  "skus", "sku_detalle", "ventas_lineas", "ventas_cabeceras",
  "ticket_detalle", "cabecera_detalle", "compras", "cajas", "caja_detalle",
];

// Escalones: PASO, 2·PASO, … MAX (req/s por endpoint).
const TASAS = [];
for (let r = PASO; r <= MAX + 1e-9; r += PASO) TASAS.push(Math.round(r * 100) / 100);

// Las tasas son decimales: se expresan por minuto para que k6 las acepte.
const stages = TASAS.flatMap((r) => [
  { duration: "3s", target: Math.round(r * 60) },
  { duration: `${ESCALON - 3}s`, target: Math.round(r * 60) },
]);

export const options = {
  setupTimeout: "60s",
  scenarios: Object.fromEntries(ESCENARIOS.map((name) => [name, {
    executor: "ramping-arrival-rate",
    exec: name,
    startRate: 0,
    timeUnit: "1m",
    stages,
    preAllocatedVUs: 5,
    maxVUs: 60,
  }])),
  thresholds: Object.assign(
    {
      errores_reales: [{ threshold: "rate<0.05", abortOnFail: true, delayAbortEval: "10s" }],
      "http_req_duration{expected_response:true}": [
        { threshold: "p(95)<3000", abortOnFail: true, delayAbortEval: "10s" },
      ],
    },
    // Desglose por escalón en el resumen.
    Object.fromEntries(TASAS.map((_, i) => [`http_req_duration{etapa:${i + 1}}`, ["p(95)<60000"]])),
    Object.fromEntries(TASAS.map((_, i) => [`errores_reales{etapa:${i + 1}}`, ["rate<=1"]])),
  ),
  summaryTrendStats: ["med", "p(95)", "p(99)", "max"],
};

export function setup() {
  const login = http.post(`${BASE}/auth/token`, { username: __ENV.USERNAME, password: __ENV.PASSWORD });
  if (login.status !== 200) fail(`login falló: ${login.status}`);
  const headers = { Authorization: `Bearer ${login.json("access_token")}` };
  const primero = (path) => {
    const r = http.get(`${BASE}${path}`, { headers });
    const items = r.status === 200 ? r.json("items") : [];
    return items && items.length ? items[0] : null;
  };
  const sku = primero("/api/skus?limit=1");
  const ticket = primero(`/api/ventas?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=1`);
  const caja = primero("/api/cajas-pendientes?limit=1");
  console.log(`escalones (req/s por endpoint): ${TASAS.join(", ")} · total ×${ESCENARIOS.length}`);
  return { headers, sku: sku && sku.sku, ticket, caja: caja && caja.codigo_caja };
}

function get(d, path) {
  const etapa = String(Math.min(TASAS.length, Math.floor(exec.instance.currentTestRunDuration / 1000 / ESCALON) + 1));
  const r = http.get(`${BASE}${path}`, {
    headers: d.headers,
    tags: { etapa },
    responseCallback: http.expectedStatuses(200),
    timeout: "30s",
  });
  if (r.status === 429) limitadas.add(1, { etapa });
  errores.add(r.status !== 200 && r.status !== 429, { etapa });
}

const SKU_QS = [
  "limit=50",
  "con_stock=true&orden=pvp&direccion=desc&limit=100",
  "q=camis&limit=50",
];
export function skus(d) { get(d, `/api/skus?${SKU_QS[exec.scenario.iterationInTest % SKU_QS.length]}`); }
export function sku_detalle(d) { if (d.sku) get(d, `/api/skus/${encodeURIComponent(d.sku)}`); }
export function ventas_lineas(d) { get(d, `/api/ventas?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=100`); }
export function ventas_cabeceras(d) { get(d, `/api/ventas/cabeceras?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=100`); }
const clave = (t) => `${t.fldIdEmpresa}/${t.fldIdAlmacen}/${t.fldIdCaja}/${t.fldIdTicket}`;
export function ticket_detalle(d) { if (d.ticket) get(d, `/api/ventas/ticket/${clave(d.ticket)}`); }
export function cabecera_detalle(d) { if (d.ticket) get(d, `/api/ventas/cabecera/${clave(d.ticket)}`); }
export function compras(d) { get(d, `/api/compras?fecha_desde=${FECHA_DESDE}&fecha_hasta=${FECHA_HASTA}&limit=100`); }
export function cajas(d) { get(d, "/api/cajas-pendientes?limit=100"); }
export function caja_detalle(d) { if (d.caja) get(d, `/api/cajas-pendientes/caja/${encodeURIComponent(d.caja)}`); }
