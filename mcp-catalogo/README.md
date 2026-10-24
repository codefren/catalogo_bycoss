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

## Conectarlo a Claude Desktop

Edita el archivo de configuración de Claude Desktop (en Windows):

`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "catalogo-bycoss": {
      "command": "C:\\Users\\efarr\\OneDrive\\Proyectos\\databricks\\mcp-catalogo\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\efarr\\OneDrive\\Proyectos\\databricks\\mcp-catalogo\\server.py"]
    }
  }
}
```

(Las credenciales las toma del `.env` junto a `server.py`; si prefieres, puedes
ponerlas en un bloque `"env": { ... }` aquí en vez del `.env`.)

Reinicia Claude Desktop y pregúntale, por ejemplo:
*"¿Cuánto stock hay del artículo 0100228002 en la tienda 00000207?"* — debería
llamar a `buscar_skus` y sumar el stock.

## Siguiente paso

En la **fase 2** este mismo servidor se conecta al agente **Hermes (Ollama)**
del chat propio: un puente traduce estas herramientas MCP al formato de
*function calling* que entiende Hermes.
