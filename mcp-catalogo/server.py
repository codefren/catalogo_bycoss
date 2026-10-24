"""Servidor MCP del Catálogo bycoss.

Expone la Catálogo API (solo lectura) como herramientas MCP para que un agente
—Claude Desktop, o Hermes vía Ollama— consulte stock, SKU, ventas, compras y
cajas pendientes en lenguaje natural. No escribe ni modifica nada.

Credenciales por variables de entorno (ver .env.example):
  CATALOGO_USER, CATALOGO_PASSWORD  (obligatorias)
  CATALOGO_BASE_URL                 (opcional)

Arranque (transporte stdio, el estándar para clientes MCP):
  python server.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from catalogo_client import CatalogoClient, CatalogoError

# Carga el .env que está junto a este archivo (no depende del cwd del cliente).
load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("catalogo-bycoss")

_api: CatalogoClient | None = None
MAX_FILAS_TOPE = 5000  # tope duro por si el agente pide demasiado


def api() -> CatalogoClient:
    """Cliente perezoso: se crea en la primera llamada (ya con el .env cargado)."""
    global _api
    if _api is None:
        _api = CatalogoClient()
    return _api


def _tope(max_filas: int) -> int:
    return max(1, min(int(max_filas), MAX_FILAS_TOPE))


# ─────────────────────────────────────────────────────────────────────────────
#  Catálogo / stock por SKU
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
async def buscar_skus(
    q: Annotated[str | None, Field(description="Texto en la descripción del artículo (contiene, sin distinguir mayúsculas).")] = None,
    articulo: Annotated[list[str] | None, Field(description="Uno o varios códigos de artículo (fldIdArticulo). Devuelve todas sus permutas color/talla.")] = None,
    almacen: Annotated[list[str] | None, Field(description="Uno o varios códigos de almacén/tienda (fldIdAlmacen), p. ej. '00000207'.")] = None,
    codigo_barras: Annotated[list[str] | None, Field(description="Uno o varios EAN exactos.")] = None,
    referencia: Annotated[list[str] | None, Field(description="Una o varias referencias de proveedor (fldReferencia).")] = None,
    temporada: Annotated[list[str] | None, Field(description="Una o varias temporadas (p. ej. 'V25').")] = None,
    familia: Annotated[list[str] | None, Field(description="Uno o varios códigos de familia.")] = None,
    marca: Annotated[list[str] | None, Field(description="Uno o varios códigos de marca.")] = None,
    color: Annotated[list[str] | None, Field(description="Uno o varios códigos de color.")] = None,
    talla: Annotated[list[str] | None, Field(description="Una o varias tallas.")] = None,
    con_stock: Annotated[bool, Field(description="Si es true, solo SKUs con stock_disponible > 0.")] = False,
    orden: Annotated[str, Field(description="Ordenación: 'sku', 'articulo', 'pvp', 'stock' o 'actualizado'.")] = "sku",
    max_filas: Annotated[int, Field(description="Máximo de filas a devolver (pagina sola si hace falta).")] = 200,
) -> list[dict]:
    """Busca SKUs del catálogo. Una fila por SKU Y almacén (un mismo SKU aparece
    una vez por cada almacén que lo tiene).

    Úsalo para: stock por artículo, buscar por descripción (`q`), por código de
    barras o referencia, o listar las permutas color/talla de un artículo.
    Para el stock total de un artículo en una tienda, filtra por `articulo` y
    `almacen` y SUMA `stock_disponible` de las filas devueltas. Cada fila trae
    `total_transito` (unidades en camino) y `stock_disponible`.
    """
    params = {
        "q": q,
        "articulo": articulo,
        "almacen": almacen,
        "codigo_barras": codigo_barras,
        "referencia": referencia,
        "temporada": temporada,
        "familia": familia,
        "marca": marca,
        "color": color,
        "talla": talla,
        "con_stock": con_stock or None,
        "orden": orden,
    }
    return await api().paginar("/api/skus", params, max_filas=_tope(max_filas))


@mcp.tool()
async def obtener_sku(
    sku: Annotated[str, Field(description="Código de SKU exacto, p. ej. '0100228002-000005-U'.")],
    almacen: Annotated[list[str] | None, Field(description="Opcional: limita a uno o varios almacenes.")] = None,
) -> list[dict]:
    """Devuelve las filas de UN SKU, una por almacén. Para el stock total del
    SKU en todas las tiendas, suma `stock_disponible`. Error si no existe."""
    return await api().paginar(
        f"/api/skus/{sku}", {"almacen": almacen}, max_filas=MAX_FILAS_TOPE
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Stock por almacén (con nombre de tienda)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
async def stock_por_tienda(
    articulo: Annotated[list[str] | None, Field(description="Uno o varios códigos de artículo.")] = None,
    almacen: Annotated[list[str] | None, Field(description="Uno o varios códigos de almacén/tienda.")] = None,
    almacen_nombre: Annotated[str | None, Field(description="Busca en el nombre de la tienda (contiene, sin distinguir mayúsculas).")] = None,
    color: Annotated[list[str] | None, Field(description="Uno o varios códigos de color.")] = None,
    talla: Annotated[list[str] | None, Field(description="Una o varias tallas.")] = None,
    con_stock: Annotated[bool, Field(description="Si es true, solo filas con stock_disponible > 0.")] = False,
    max_filas: Annotated[int, Field(description="Máximo de filas a devolver.")] = 200,
) -> list[dict]:
    """Stock por artículo-color-talla y almacén, incluyendo el NOMBRE de la
    tienda (`almacen_descripcion`). El stock puede ser negativo. Trae también
    `total_transito`. Úsalo cuando necesites el nombre de la tienda; si solo
    quieres códigos, `buscar_skus` también da el stock."""
    params = {
        "articulo": articulo,
        "almacen": almacen,
        "almacen_nombre": almacen_nombre,
        "color": color,
        "talla": talla,
        "con_stock": con_stock or None,
    }
    return await api().paginar("/api/stock", params, max_filas=_tope(max_filas))


@mcp.tool()
async def listar_almacenes() -> list[dict]:
    """Lista completa de almacenes/tiendas con su código (`fldIdAlmacen`) y
    nombre (`almacen_descripcion`). Úsala para poner nombre a un código de
    tienda de cualquier otro endpoint. Algunos vienen sin descripción (null)."""
    page = await api().get("/api/stock/almacenes")
    return page.get("items", []) if isinstance(page, dict) else []


# ─────────────────────────────────────────────────────────────────────────────
#  Ventas
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
async def ventas_lineas(
    fecha_desde: Annotated[str | None, Field(description="Fecha inicial inclusive, 'YYYY-MM-DD'.")] = None,
    fecha_hasta: Annotated[str | None, Field(description="Fecha final inclusive, 'YYYY-MM-DD'.")] = None,
    almacen: Annotated[str | None, Field(description="Código de almacén/tienda.")] = None,
    sku: Annotated[str | None, Field(description="SKU vendido.")] = None,
    ticket: Annotated[str | None, Field(description="fldIdTicket (no es único entre tiendas/cajas).")] = None,
    cliente: Annotated[str | None, Field(description="fldIdCliente.")] = None,
    max_filas: Annotated[int, Field(description="Máximo de filas (líneas) a devolver.")] = 200,
) -> list[dict]:
    """Líneas de venta (una fila por línea de ticket). Para unidades vendidas de
    un SKU en un periodo, filtra y SUMA `fldCantidad`. OJO: para totales por
    ticket (importe, nº de tickets) usa `ventas_cabeceras`, no sumes líneas.
    La talla aquí se llama `fldTalla`."""
    params = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "almacen": almacen,
        "sku": sku,
        "ticket": ticket,
        "cliente": cliente,
    }
    return await api().paginar("/api/ventas", params, max_filas=_tope(max_filas))


@mcp.tool()
async def ventas_cabeceras(
    fecha_desde: Annotated[str | None, Field(description="Fecha inicial inclusive, 'YYYY-MM-DD'.")] = None,
    fecha_hasta: Annotated[str | None, Field(description="Fecha final inclusive, 'YYYY-MM-DD'.")] = None,
    almacen: Annotated[str | None, Field(description="Código de almacén/tienda.")] = None,
    cliente: Annotated[str | None, Field(description="fldIdCliente.")] = None,
    ticket: Annotated[str | None, Field(description="fldIdTicket.")] = None,
    max_filas: Annotated[int, Field(description="Máximo de tickets a devolver.")] = 200,
) -> list[dict]:
    """Cabeceras de ticket (una fila por ticket, con sus totales sin duplicar
    por línea). Úsalo para facturación (suma `fldImporteNeto`), nº de tickets
    (nº de filas) y ticket medio."""
    params = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "almacen": almacen,
        "cliente": cliente,
        "ticket": ticket,
    }
    return await api().paginar(
        "/api/ventas/cabeceras", params, max_filas=_tope(max_filas)
    )


@mcp.tool()
async def obtener_ticket(
    empresa: Annotated[str, Field(description="fldIdEmpresa.")],
    almacen: Annotated[str, Field(description="fldIdAlmacen.")],
    caja: Annotated[str, Field(description="fldIdCaja.")],
    ticket: Annotated[str, Field(description="fldIdTicket.")],
) -> list[dict]:
    """Todas las líneas de un ticket por su clave natural completa
    (empresa, almacén, caja, ticket). Error si no hay líneas."""
    return await api().paginar(
        f"/api/ventas/ticket/{empresa}/{almacen}/{caja}/{ticket}",
        max_filas=MAX_FILAS_TOPE,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Compras
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
async def compras(
    fecha_desde: Annotated[str | None, Field(description="Fecha inicial inclusive, 'YYYY-MM-DD'.")] = None,
    fecha_hasta: Annotated[str | None, Field(description="Fecha final inclusive, 'YYYY-MM-DD'.")] = None,
    almacen: Annotated[str | None, Field(description="Código de almacén/tienda.")] = None,
    proveedor: Annotated[str | None, Field(description="fldIdProveedor.")] = None,
    articulo: Annotated[str | None, Field(description="Código de artículo.")] = None,
    color: Annotated[str | None, Field(description="Código de color.")] = None,
    talla: Annotated[str | None, Field(description="Talla.")] = None,
    temporada: Annotated[str | None, Field(description="Temporada.")] = None,
    familia: Annotated[str | None, Field(description="Código de familia.")] = None,
    max_filas: Annotated[int, Field(description="Máximo de filas a devolver.")] = 200,
) -> list[dict]:
    """Compras a proveedores (una fila por artículo-color-talla comprado), con
    el nombre del proveedor. Para unidades compradas, suma `cantidad`."""
    params = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "almacen": almacen,
        "proveedor": proveedor,
        "articulo": articulo,
        "color": color,
        "talla": talla,
        "temporada": temporada,
        "familia": familia,
    }
    return await api().paginar("/api/compras", params, max_filas=_tope(max_filas))


# ─────────────────────────────────────────────────────────────────────────────
#  Cajas pendientes (mercancía en tránsito a tienda)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
async def cajas_pendientes(
    tienda: Annotated[str | None, Field(description="Código de tienda.")] = None,
    cliente: Annotated[str | None, Field(description="Código de cliente (cod_cliente).")] = None,
    articulo: Annotated[str | None, Field(description="Código de artículo.")] = None,
    ean: Annotated[str | None, Field(description="Código de barras (EAN).")] = None,
    caja: Annotated[str | None, Field(description="codigo_caja.")] = None,
    pedido: Annotated[str | None, Field(description="no_pedido.")] = None,
    envio: Annotated[str | None, Field(description="no_envio.")] = None,
    dispatch_note: Annotated[str | None, Field(description="Albarán (dispatch_note).")] = None,
    max_filas: Annotated[int, Field(description="Máximo de filas a devolver.")] = 200,
) -> list[dict]:
    """Mercancía enviada a tienda que AÚN NO ha llegado (una fila por
    artículo-color-talla dentro de una caja). Para saber qué viene en camino a
    una tienda o de un producto. Para unidades suma `cantidad` (no `total_prendas`,
    que se repite por caja). Las fechas son texto tal cual vienen del origen."""
    params = {
        "tienda": tienda,
        "cliente": cliente,
        "articulo": articulo,
        "ean": ean,
        "caja": caja,
        "pedido": pedido,
        "envio": envio,
        "dispatch_note": dispatch_note,
    }
    return await api().paginar(
        "/api/cajas-pendientes", params, max_filas=_tope(max_filas)
    )


@mcp.tool()
async def estado_api() -> dict:
    """Comprueba que la Catálogo API responde (GET /health, sin auth)."""
    try:
        return await api().get("/health")
    except CatalogoError as e:
        return {"status": "error", "detalle": str(e)}


if __name__ == "__main__":
    mcp.run()
