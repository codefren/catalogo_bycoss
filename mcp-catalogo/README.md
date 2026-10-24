# MCP Catálogo bycoss

Servidor **MCP** (Model Context Protocol) que expone la [Catálogo API](../docs/endpoints.md)
de solo lectura como **herramientas** para un agente: stock, SKU, ventas,
compras y cajas pendientes. Sirve tanto para **Claude Desktop** como, más
adelante, para el **agente Hermes (Ollama)** del chat propio.

El servidor nunca escribe ni modifica datos: la API es de solo lectura.

## Herramientas que expone

| Herramienta | Qué hace |
|---|---|
| `buscar_skus` | Busca SKUs (stock por artículo, por descripción, EAN, referencia…). |
| `obtener_sku` | Filas de un SKU concreto, una por almacén. |
| `stock_por_tienda` | Stock por tienda con el **nombre** del almacén. |
| `listar_almacenes` | Catálogo de tiendas (código → nombre). |
| `ventas_lineas` | Líneas de venta (unidades por SKU/periodo). |
| `ventas_cabeceras` | Tickets con totales (facturación, nº de tickets). |
| `obtener_ticket` | Líneas de un ticket por su clave natural. |
| `compras` | Compras a proveedores. |
| `cajas_pendientes` | Mercancía en tránsito a tienda (lo que viene en camino). |
| `estado_api` | Comprueba que la API responde (`/health`). |

## Instalación

Desde esta carpeta (`mcp-catalogo/`):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Credenciales

Copia `.env.example` a `.env` y rellena tu usuario/contraseña de la API:

```bash
copy .env.example .env
```

```
CATALOGO_BASE_URL=https://bycos.data4tex.com
CATALOGO_USER=bycos
CATALOGO_PASSWORD=tu-contraseña
```

El `.env` está en `.gitignore`: **no se sube a git**. El servidor hace el login
y renueva el token (JWT) solo.

## Probar que funciona

Comprueba que las dependencias y el import están bien:

```bash
python -c "import server; print('OK', [t for t in server.mcp._tool_manager.list_tools()])"
```

Para un arranque real, un cliente MCP lanza `python server.py` (transporte
stdio) y se comunica por stdin/stdout.

El servidor funciona de **dos modos**, con el mismo código:

| Modo | Transporte | Cómo se arranca |
|---|---|---|
| **Local** | stdio | Lo lanza el cliente MCP (`python server.py`). |
| **Remoto (prod)** | Streamable HTTP en `/mcp` | `uvicorn server:app` dentro de Docker, detrás de Caddy. |

## Opción A — Local (stdio)

Edita `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "catalogo-bycoss": {
      "command": "C:\\Users\\efarr\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": ["C:\\Users\\efarr\\OneDrive\\Proyectos\\databricks\\mcp-catalogo\\server.py"]
    }
  }
}
```

Las credenciales se toman del `.env` junto a `server.py`. Reinicia Claude
Desktop y pregúntale algo de stock.

## Opción B — Remoto, desplegado en producción

El servidor corre como un contenedor más del `docker-compose.yml`, detrás de
Caddy, en `https://mcp-bycos.data4tex.com/mcp`. Protegido con un **token**
(`MCP_API_KEY`): sin él, `401`.

### 1. Token y variables (en el `.env` de la RAÍZ del proyecto)

```bash
# genera un token
openssl rand -hex 32
```

Añade al `.env` raíz (el que lee docker-compose):

```
MCP_API_KEY=<el-token-generado>
```

`CATALOGO_USER` y `CATALOGO_PASSWORD` ya están ahí; `CATALOGO_BASE_URL` lo fija
el compose a `http://api:8000` (red interna).

### 2. DNS

Registro A: `mcp-bycos` → IP del servidor (`82.223.234.89`). ✅ (ya creado)

### 3. Caddy

En tu Caddyfile (Caddy debe estar en la red `edge`):

```caddy
mcp-bycos.data4tex.com {
    reverse_proxy databricks-catalog-mcp:8000
}
```

Recarga Caddy. El TLS lo gestiona Caddy automáticamente.

### 4. Desplegar

En el servidor:

```bash
docker compose up -d --build mcp
docker compose logs -f mcp
```

### 5. Conectar Claude Desktop (al MCP remoto)

Con el puente `mcp-remote` (requiere Node/`npx` en tu PC), en
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "catalogo-bycoss": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "https://mcp-bycos.data4tex.com/mcp",
        "--header", "Authorization: Bearer EL_MCP_API_KEY"
      ]
    }
  }
}
```

(Si tu versión de Claude Desktop soporta conectores remotos nativos, también
puedes añadirlo desde Ajustes → Conectores con esa URL.)

## Siguiente paso

En la **fase 2** este mismo servidor se conecta al agente **Hermes (Ollama)**
del chat propio: un puente traduce estas herramientas MCP al formato de
*function calling* que entiende Hermes. Da igual que el MCP sea local o remoto.
