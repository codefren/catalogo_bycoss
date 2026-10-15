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
#  Autenticación — respuesta de /auth/token
# ─────────────────────────────────────────────────────────────────────────────
class TokenOut(BaseModel):
    """Par de tokens emitido en el login y en el refresh."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 43200,
                "refresh_token": "Xq3f9...token-opaco-largo...7bZ",
                "refresh_expires_in": 604800,
            }
        }
    )

    access_token: str = Field(..., description="JWT firmado (HS256).")
    token_type: str = Field("bearer", description="Tipo de token (siempre 'bearer').")
    expires_in: int = Field(..., description="Segundos hasta la caducidad del access token (12 h = 43200).")
    refresh_token: str = Field(..., description="Refresh token opaco para renovar sin re-login.")
    refresh_expires_in: int = Field(..., description="Segundos hasta la caducidad del refresh token (7 d = 604800).")


class RefreshIn(BaseModel):
    """Cuerpo de /auth/refresh y /auth/logout."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"refresh_token": "Xq3f9...token-opaco-largo...7bZ"}}
    )

    refresh_token: str = Field(..., description="Refresh token recibido en el login o en el refresh anterior.")

# ─────────────────────────────────────────────────────────────────────────────
#  Ejemplos realistas que se muestran en Swagger (el "Example Value" del 200).
#  Son valores ILUSTRATIVOS, no datos reales; sirven para ver la forma de la
#  respuesta con contenido legible en vez de "string"/0.
# ─────────────────────────────────────────────────────────────────────────────
_SKU_EXAMPLE = {
    "sku": "001234-05-M",
    "fldIdArticulo": "001234",
    "articulo_descripcion": "Camiseta manga corta",
    "fldTemporada": "V25",
    "fldIdFamilia": "CAM",
    "fldIdProveedor": "PROV012",
    "fldReferencia": "REF-55120",
    "fldColeccion": "Primavera-Verano 2025",
    "fldMinimoStock": 5,
    "fldMaximoStock": 50,
    "fldPuntoPedido": 10,
    "fldIdMarca": "BYC",
    "fldIdSexo": "H",
    "fldIdGrupo": "G01",
    "fldIdSubgrupo": "SG03",
    "fldIdSubfamilia": "SF07",
    "fldIdTemporadaVenta": "V25",
    "fldIdColor": "05",
    "color_descripcion": "Azul marino",
    "fldIdGrupoTallas": "GT1",
    "grupotalla_descripcion": "Tallas S-XXL",
    "talla": "M",
    "total_entradas": 120,
    "total_salidas": 97,
    "total_servicio": 0,
    "total_transito": 0,
    "stock_disponible": 23,
    "num_almacenes": 3,
    "actualizado_en": "2025-10-14T02:11:00",
}

_TICKET_EXAMPLE = {
    "fldIdEmpresa": "0001",
    "fldIdAlmacen": "00000207",
    "fldIdCaja": "000001",
    "fldIdTicket": "2072056051",
    "fldLinea": "0001",
    "fecha": "2025-07-14",
    "fldHora": "19:26:44",
    "fldIdCliente": "00000001",
    "fldIdOperario": "00010",
    "fldIdCajera": "00010",
    "fldPrendas": 2,
    "fldImporteBruto": 59.90,
    "fldImporteDto": 0,
    "fldImporteNeto": 59.90,
    "fldCobradoTicket": 59.90,
    "fldPteTicket": 0,
    "fldIdMoneda": "EUR",
    "fldCambio": 1,
    "dto_cabecera": 0,
    "id_cierre": "C20250714",
    "fldVales": 0,
    "fldApartados": 0,
    "fldArreglos": 0,
    "fldPromociones": 0,
    "fldChequeRegalo": 0,
    "fldCupones": 0,
    "fldEspecial": 0,
    "fldIdVale": "",
    "fldIdArticulo": "001234",
    "fldIdColor": "05",
    "fldTalla": "M",
    "sku": "001234-05-M",
    "fldCantidad": 1,
    "fldPrecio": 29.95,
    "dto_linea": 0,
    "importe_linea": 29.95,
    "fldIdPromocion": "",
    "fldIdPromoCat": "",
    "fldIVA": 21,
    "fldVentaReal": 1,
    "fldIdRebaja": "",
    "actualizado_en": "2025-07-14T23:00:00",
}


# ─────────────────────────────────────────────────────────────────────────────
#  SKU — catálogo de artículos a nivel artículo-color-talla
# ─────────────────────────────────────────────────────────────────────────────
class SkuOut(BaseModel):
    """Una referencia del catálogo (grano: artículo + color + talla)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _SKU_EXAMPLE},
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [_SKU_EXAMPLE], "count": 1, "limit": 50, "offset": 0}
        }
    )

    items: list[SkuOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")


# ─────────────────────────────────────────────────────────────────────────────
#  TICKET_MAESTRO — líneas de ticket (ventas). Grano: una fila por línea.
# ─────────────────────────────────────────────────────────────────────────────
class TicketLineaOut(BaseModel):
    """Una línea de ticket de venta."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _TICKET_EXAMPLE},
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [_TICKET_EXAMPLE], "count": 1, "limit": 50, "offset": 0}
        }
    )

    items: list[TicketLineaOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")
