"""Modelos Pydantic de respuesta.

Definen el contrato público de la API y, de paso, lo que aparece documentado en
Swagger (/docs) y en el esquema OpenAPI (/openapi.json). Los nombres de campo
coinciden EXACTAMENTE con las columnas de Postgres (camelCase con prefijo `fld`),
así que `SELECT *` mapea directo sin renombrar.

Todas las columnas son nullable en la base, por eso todos los campos son
opcionales (`| None`).
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
#  SKU — catálogo de artículos a nivel artículo-color-talla
# ─────────────────────────────────────────────────────────────────────────────
class SkuOut(BaseModel):
    """Una referencia del catálogo (grano: artículo + color + talla)."""

    model_config = ConfigDict(from_attributes=True)

    sku: str | None = Field(None, description="Código único de SKU (artículo-color-talla).")
    fldIdArticulo: str | None = Field(None, description="Código de artículo.")
    articulo_descripcion: str | None = Field(None, description="Descripción del artículo.")
    fldTemporada: str | None = Field(None, description="Temporada del artículo.")
    fldIdFamilia: str | None = Field(None, description="Código de familia.")
    fldIdProveedor: str | None = Field(None, description="Código de proveedor.")
    fldReferencia: str | None = Field(None, description="Referencia del proveedor/fabricante.")
    fldColeccion: str | None = Field(None, description="Colección.")
    fldMinimoStock: float | None = Field(None, description="Stock mínimo configurado.")
    fldMaximoStock: float | None = Field(None, description="Stock máximo configurado.")
    fldPuntoPedido: float | None = Field(None, description="Punto de pedido.")
    fldIdMarca: str | None = Field(None, description="Código de marca.")
    fldIdSexo: str | None = Field(None, description="Código de sexo/segmento.")
    fldIdGrupo: str | None = Field(None, description="Código de grupo.")
    fldIdSubgrupo: str | None = Field(None, description="Código de subgrupo.")
    fldIdSubfamilia: str | None = Field(None, description="Código de subfamilia.")
    fldIdTemporadaVenta: str | None = Field(None, description="Temporada de venta.")
    fldIdColor: str | None = Field(None, description="Código de color.")
    color_descripcion: str | None = Field(None, description="Descripción del color.")
    fldIdGrupoTallas: str | None = Field(None, description="Código del grupo de tallas.")
    grupotalla_descripcion: str | None = Field(None, description="Descripción del grupo de tallas.")
    talla: str | None = Field(None, description="Talla.")
    total_entradas: float | None = Field(None, description="Total de entradas acumuladas.")
    total_salidas: float | None = Field(None, description="Total de salidas acumuladas.")
    total_servicio: float | None = Field(None, description="Total en servicio.")
    total_transito: float | None = Field(None, description="Total en tránsito.")
    stock_disponible: float | None = Field(None, description="Stock disponible calculado.")
    num_almacenes: int | None = Field(None, description="Nº de almacenes con existencias.")
    actualizado_en: datetime | None = Field(None, description="Última actualización del registro.")


class SkuPage(BaseModel):
    """Página de resultados de SKU."""

    items: list[SkuOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")


# ─────────────────────────────────────────────────────────────────────────────
#  TICKET_MAESTRO — líneas de ticket (ventas). Grano: una fila por línea.
# ─────────────────────────────────────────────────────────────────────────────
class TicketLineaOut(BaseModel):
    """Una línea de ticket de venta."""

    model_config = ConfigDict(from_attributes=True)

    # ── Cabecera del ticket ──────────────────────────────────────────────────
    fldIdEmpresa: str | None = Field(None, description="Código de empresa.")
    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda.")
    fldIdCaja: str | None = Field(None, description="Código de caja/TPV.")
    fldIdTicket: str | None = Field(None, description="Número de ticket.")
    fldLinea: str | None = Field(None, description="Número de línea dentro del ticket.")
    fecha: date | None = Field(None, description="Fecha del ticket.")
    fldHora: str | None = Field(None, description="Hora del ticket.")
    fldIdCliente: str | None = Field(None, description="Código de cliente.")
    fldIdOperario: str | None = Field(None, description="Código de operario.")
    fldIdCajera: str | None = Field(None, description="Código de cajera/o.")
    fldPrendas: float | None = Field(None, description="Nº de prendas del ticket.")
    fldImporteBruto: float | None = Field(None, description="Importe bruto del ticket.")
    fldImporteDto: float | None = Field(None, description="Descuento del ticket.")
    fldImporteNeto: float | None = Field(None, description="Importe neto del ticket.")
    fldCobradoTicket: float | None = Field(None, description="Importe cobrado.")
    fldPteTicket: float | None = Field(None, description="Importe pendiente.")
    fldIdMoneda: str | None = Field(None, description="Código de moneda.")
    fldCambio: float | None = Field(None, description="Tipo de cambio aplicado.")
    dto_cabecera: float | None = Field(None, description="Descuento de cabecera.")
    id_cierre: str | None = Field(None, description="Identificador de cierre de caja.")
    fldVales: int | None = Field(None, description="Nº de vales.")
    fldApartados: int | None = Field(None, description="Nº de apartados.")
    fldArreglos: int | None = Field(None, description="Nº de arreglos.")
    fldPromociones: int | None = Field(None, description="Nº de promociones.")
    fldChequeRegalo: int | None = Field(None, description="Nº de cheques regalo.")
    fldCupones: float | None = Field(None, description="Importe de cupones.")
    fldEspecial: float | None = Field(None, description="Importe especial.")
    # ── Detalle de la línea ──────────────────────────────────────────────────
    fldIdVale: str | None = Field(None, description="Identificador de vale.")
    fldIdArticulo: str | None = Field(None, description="Código de artículo de la línea.")
    fldIdColor: str | None = Field(None, description="Código de color de la línea.")
    fldTalla: str | None = Field(None, description="Talla de la línea.")
    sku: str | None = Field(None, description="SKU vendido (enlaza con el catálogo sku).")
    fldCantidad: float | None = Field(None, description="Cantidad vendida.")
    fldPrecio: float | None = Field(None, description="Precio unitario.")
    dto_linea: float | None = Field(None, description="Descuento de la línea.")
    importe_linea: float | None = Field(None, description="Importe de la línea.")
    fldIdPromocion: str | None = Field(None, description="Código de promoción.")
    fldIdPromoCat: str | None = Field(None, description="Categoría de promoción.")
    fldIVA: float | None = Field(None, description="IVA aplicado.")
    fldVentaReal: int | None = Field(None, description="Indicador de venta real.")
    fldIdRebaja: str | None = Field(None, description="Código de rebaja.")
    actualizado_en: datetime | None = Field(None, description="Última actualización del registro.")


class TicketPage(BaseModel):
    """Página de resultados de líneas de ticket."""

    items: list[TicketLineaOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")
