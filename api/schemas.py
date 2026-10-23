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
    "fldIdAlmacen": "00000207",
    "fldIdArticulo": "001234",
    "articulo_descripcion": "Camiseta manga corta",
    "fldTemporada": "V25",
    "fldIdFamilia": "CAM",
    "fldIdSexo": "01",
    "fldReferencia": "REF-55120",
    "codigo_barras": "8412345678905",
    "fldColeccion": "Primavera-Verano 2025",
    "fldIdMarca": "BYC",
    "fldIdColor": "05",
    "color_descripcion": "Azul marino",
    "fldIdGrupoTallas": "GT1",
    "grupotalla_descripcion": "Tallas S-XXL",
    "talla": "M",
    "pvp": 29.95,
    "precio_costo": 11.40,
    "total_transito": 12,
    "stock_disponible": 23,
    "actualizado_en": "2025-10-14T02:11:00",
}

_STOCK_EXAMPLE = {
    "fldIdAlmacen": "00000207",
    "almacen_descripcion": "TIENDA CENTRO",
    "fldIdArticulo": "001234",
    "fldIdColor": "05",
    "talla": "M",
    "stock_disponible": 23,
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
    "fldIdMoneda": "EUR",
    "fldCambio": 1,
    "fldIdArticulo": "001234",
    "fldIdColor": "05",
    "fldTalla": "M",
    "sku": "001234-05-M",
    "fldCantidad": 1,
    "fldPrecio": 29.95,
    "dto_linea": 0,
    "importe_linea": 29.95,
    "fldIVA": 21,
    "actualizado_en": "2025-07-14T23:00:00",
}
_CABECERA_EXAMPLE = {
    "fldIdEmpresa": "0001",
    "fldIdAlmacen": "00000207",
    "fldIdCaja": "000001",
    "fldIdTicket": "2072056051",
    "fecha": "2025-07-14",
    "fldHora": "19:26:44",
    "fldIdCliente": "00000001",
    "fldIdMoneda": "EUR",
    "fldCambio": 1,
    "fldPrendas": 2,
    "fldImporteBruto": 59.90,
    "fldImporteDto": 0,
    "fldImporteNeto": 59.90,
    "fldCobradoTicket": 59.90,
    "fldPteTicket": 0,
    "dto_cabecera": 0,
    "fldVales": 0,
    "fldApartados": 0,
    "fldArreglos": 0,
    "fldPromociones": 0,
    "fldChequeRegalo": 0,
    "fldCupones": 0,
    "fldEspecial": 0,
}
_COMPRA_EXAMPLE = {
    "fldIdEmpresa": "0001",
    "fldIdAlmacen": "00000207",
    "fldIdProveedor": "PROV012",
    "nombre_proveedor": "Textiles del Norte, S.L.",
    "fecha": "2025-06-30",
    "fldIdArticulo": "001234",
    "fldIdColor": "05",
    "talla_pos": 3,
    "talla": "M",
    "cantidad": 24.0,
    "fldIdMoneda": "EUR",
    "fldCambio": 1.0,
    "descripcion_articulo": "Camiseta manga corta",
    "fldTemporada": "V25",
    "fldIdFamilia": "CAM",
    "fldIdGrupoTallas": "GT1",
    "descripcion_grupo_tallas": "Tallas S-XXL",
}


# ─────────────────────────────────────────────────────────────────────────────
#  SKU — catálogo de artículos a nivel artículo-color-talla
# ─────────────────────────────────────────────────────────────────────────────
class SkuOut(BaseModel):
    """Una referencia del catálogo en un almacén (grano: artículo + color +
    talla + almacén)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _SKU_EXAMPLE},
    )

    sku: str | None = Field(None, description="Código de SKU (artículo-color-talla).")
    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda de esta fila.")
    fldIdArticulo: str | None = Field(None, description="Código de artículo.")
    articulo_descripcion: str | None = Field(None, description="Descripción del artículo.")
    fldTemporada: str | None = Field(None, description="Temporada del artículo.")
    fldIdFamilia: str | None = Field(None, description="Código de familia.")
    fldIdSexo: str | None = Field(None, description="Código de sexo (solo código; no hay tabla de descripciones).")
    fldReferencia: str | None = Field(None, description="Referencia del proveedor/fabricante.")
    codigo_barras: str | None = Field(None, description="Código de barras (EAN) del SKU.")
    fldColeccion: str | None = Field(None, description="Colección.")
    fldIdMarca: str | None = Field(None, description="Código de marca.")
    fldIdColor: str | None = Field(None, description="Código de color.")
    color_descripcion: str | None = Field(None, description="Descripción del color.")
    fldIdGrupoTallas: str | None = Field(None, description="Código del grupo de tallas.")
    grupotalla_descripcion: str | None = Field(None, description="Descripción del grupo de tallas.")
    talla: str | None = Field(None, description="Talla.")
    pvp: float | None = Field(None, description="Precio de venta al público.")
    precio_costo: float | None = Field(None, description="Precio de coste unitario (coste actual, no histórico).")
    total_transito: float | None = Field(None, description="Unidades en tránsito (pedidas, aún no recibidas en el almacén).")
    stock_disponible: float | None = Field(None, description="Stock disponible en este almacén.")
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
#  STOCK — stock por almacén. Grano: una fila por artículo-color-talla y almacén.
# ─────────────────────────────────────────────────────────────────────────────
class StockOut(BaseModel):
    """Stock de un artículo-color-talla en un almacén."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _STOCK_EXAMPLE},
    )

    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda.")
    almacen_descripcion: str | None = Field(None, description="Descripción (nombre) del almacén/tienda.")
    fldIdArticulo: str | None = Field(None, description="Código de artículo.")
    fldIdColor: str | None = Field(None, description="Código de color.")
    talla: str | None = Field(None, description="Talla.")
    stock_disponible: float | None = Field(None, description="Stock disponible en este almacén (puede ser negativo).")
    actualizado_en: datetime | None = Field(None, description="Última actualización del registro.")


class StockPage(BaseModel):
    """Página de resultados de stock."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [_STOCK_EXAMPLE], "count": 1, "limit": 50, "offset": 0}
        }
    )

    items: list[StockOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")


class AlmacenOut(BaseModel):
    """Un almacén/tienda con su descripción."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"fldIdAlmacen": "00000207", "almacen_descripcion": "TIENDA CENTRO"}},
    )

    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda.")
    almacen_descripcion: str | None = Field(None, description="Descripción (nombre) del almacén/tienda.")


class AlmacenesPage(BaseModel):
    """Lista completa de almacenes (sin paginar)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [{"fldIdAlmacen": "00000207", "almacen_descripcion": "TIENDA CENTRO"}],
                "count": 1, "limit": 1, "offset": 0,
            }
        }
    )

    items: list[AlmacenOut]
    count: int = Field(..., description="Nº de almacenes devueltos.")
    limit: int = Field(..., description="Igual a count (no se pagina).")
    offset: int = Field(..., description="Siempre 0.")


# ─────────────────────────────────────────────────────────────────────────────
#  TICKET_MAESTRO — líneas de ticket (ventas). Grano: una fila por línea.
# ─────────────────────────────────────────────────────────────────────────────
class TicketLineaOut(BaseModel):
    """Una línea de ticket de venta."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _TICKET_EXAMPLE},
    )

    # ── Identidad de la línea ────────────────────────────────────────────────
    fldIdEmpresa: str | None = Field(None, description="Código de empresa.")
    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda.")
    fldIdCaja: str | None = Field(None, description="Código de caja/TPV.")
    fldIdTicket: str | None = Field(None, description="Número de ticket.")
    fldLinea: str | None = Field(None, description="Número de línea dentro del ticket.")
    fecha: date | None = Field(None, description="Fecha del ticket.")
    fldHora: str | None = Field(None, description="Hora del ticket.")
    fldIdCliente: str | None = Field(None, description="Código de cliente.")
    fldIdMoneda: str | None = Field(None, description="Código de moneda.")
    fldCambio: float | None = Field(None, description="Tipo de cambio aplicado.")
    # ── Detalle de la línea ──────────────────────────────────────────────────
    fldIdArticulo: str | None = Field(None, description="Código de artículo de la línea.")
    fldIdColor: str | None = Field(None, description="Código de color de la línea.")
    fldTalla: str | None = Field(None, description="Talla de la línea.")
    sku: str | None = Field(None, description="SKU vendido (enlaza con el catálogo sku).")
    fldCantidad: float | None = Field(None, description="Cantidad vendida.")
    fldPrecio: float | None = Field(None, description="Precio unitario.")
    dto_linea: float | None = Field(None, description="Descuento de la línea.")
    importe_linea: float | None = Field(None, description="Importe de la línea.")
    fldIVA: float | None = Field(None, description="IVA aplicado.")
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


# ─────────────────────────────────────────────────────────────────────────────
#  CABECERA DE TICKET — totales del ticket, UNA fila por ticket.
#  `ticket_maestro` tiene una fila por LÍNEA y los importes de cabecera se
#  repiten en todas las líneas del mismo ticket. Aquí se agregan por la clave
#  natural (ver routers/ventas.py) para exponerlos una sola vez, sin duplicar.
#  No incluye operario/cajera ni códigos internos (mismo criterio que la línea).
# ─────────────────────────────────────────────────────────────────────────────
class TicketCabeceraOut(BaseModel):
    """Cabecera de un ticket (totales), con una fila por ticket."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _CABECERA_EXAMPLE},
    )

    # ── Clave natural y datos de cabecera ────────────────────────────────────
    fldIdEmpresa: str | None = Field(None, description="Código de empresa.")
    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda.")
    fldIdCaja: str | None = Field(None, description="Código de caja/TPV.")
    fldIdTicket: str | None = Field(None, description="Número de ticket.")
    fecha: date | None = Field(None, description="Fecha del ticket.")
    fldHora: str | None = Field(None, description="Hora del ticket.")
    fldIdCliente: str | None = Field(None, description="Código de cliente.")
    fldIdMoneda: str | None = Field(None, description="Código de moneda.")
    fldCambio: float | None = Field(None, description="Tipo de cambio aplicado.")
    # ── Totales del ticket (una sola vez por ticket) ─────────────────────────
    fldPrendas: float | None = Field(None, description="Nº de prendas del ticket.")
    fldImporteBruto: float | None = Field(None, description="Importe bruto del ticket.")
    fldImporteDto: float | None = Field(None, description="Descuento del ticket.")
    fldImporteNeto: float | None = Field(None, description="Importe neto del ticket.")
    fldCobradoTicket: float | None = Field(None, description="Importe cobrado.")
    fldPteTicket: float | None = Field(None, description="Importe pendiente.")
    dto_cabecera: float | None = Field(None, description="Descuento de cabecera.")
    fldVales: int | None = Field(None, description="Nº de vales.")
    fldApartados: int | None = Field(None, description="Nº de apartados.")
    fldArreglos: int | None = Field(None, description="Nº de arreglos.")
    fldPromociones: int | None = Field(None, description="Nº de promociones.")
    fldChequeRegalo: int | None = Field(None, description="Nº de cheques regalo.")
    fldCupones: float | None = Field(None, description="Importe de cupones.")
    fldEspecial: float | None = Field(None, description="Importe especial.")


class TicketCabeceraPage(BaseModel):
    """Página de resultados de cabeceras de ticket."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [_CABECERA_EXAMPLE], "count": 1, "limit": 50, "offset": 0}
        }
    )

    items: list[TicketCabeceraOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")


# ─────────────────────────────────────────────────────────────────────────────
#  COMPRAS_MAESTRO — líneas de compra a proveedor.
#  Grano: una fila por artículo-color-talla comprado (sin PK declarada).
# ─────────────────────────────────────────────────────────────────────────────
class CompraOut(BaseModel):
    """Una línea de compra (tabla `compras_maestro`)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _COMPRA_EXAMPLE},
    )

    fldIdEmpresa: str | None = Field(None, description="Código de empresa.")
    fldIdAlmacen: str | None = Field(None, description="Código de almacén/tienda.")
    fldIdProveedor: str | None = Field(None, description="Código de proveedor.")
    nombre_proveedor: str | None = Field(None, description="Nombre del proveedor.")
    fecha: date | None = Field(None, description="Fecha de la compra.")
    fldIdArticulo: str | None = Field(None, description="Código de artículo.")
    fldIdColor: str | None = Field(None, description="Código de color.")
    talla_pos: int | None = Field(None, description="Posición de la talla dentro del grupo de tallas.")
    talla: str | None = Field(None, description="Talla.")
    cantidad: float | None = Field(None, description="Cantidad comprada en la línea.")
    fldIdMoneda: str | None = Field(None, description="Código de moneda.")
    fldCambio: float | None = Field(None, description="Tipo de cambio aplicado.")
    descripcion_articulo: str | None = Field(None, description="Descripción del artículo.")
    fldTemporada: str | None = Field(None, description="Temporada del artículo.")
    fldIdFamilia: str | None = Field(None, description="Código de familia.")
    fldIdGrupoTallas: str | None = Field(None, description="Código del grupo de tallas.")
    descripcion_grupo_tallas: str | None = Field(None, description="Descripción del grupo de tallas.")


class ComprasPage(BaseModel):
    """Página de resultados de líneas de compra."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [_COMPRA_EXAMPLE], "count": 1, "limit": 50, "offset": 0}
        }
    )

    items: list[CompraOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")


# ─────────────────────────────────────────────────────────────────────────────
#  CAJAS_PENDIENTES — líneas de caja/envío pendientes de llegada a tienda.
#  Grano: una fila por artículo-color-talla dentro de una caja.
#
#  NOTA: en el origen TODAS las columnas son `text` (incluidas fechas y
#  cantidades) y usan PascalCase con un typo (`DispathNote`). El router las
#  normaliza: entrega claves snake_case limpias (SELECT ... AS ...), tipa las
#  cantidades como enteros y deja las fechas como string (hasta confirmar su
#  formato real en el origen).
# ─────────────────────────────────────────────────────────────────────────────
_CAJA_EXAMPLE = {
    "cod_cliente": "C00123",
    "tienda": "00000207",
    "nombre_tienda": "BYC Gran Vía",
    "dispatch_note": "DN-2025-04815",
    "fecha_salida": "2025-10-10",
    "fecha_llegada": "2025-10-14",
    "codigo_caja": "CJ0000998877",
    "no_bulto": "1/3",
    "total_prendas": 12,
    "no_pedido": "PED-55120",
    "no_envio": "ENV-20812",
    "ean": "8412345678901",
    "articulo": "001234",
    "color": "05",
    "talla": "M",
    "descripcion_articulo": "Camiseta manga corta",
    "descripcion_color": "Azul marino",
    "marca": "BYC",
    "familia": "CAM",
    "descripcion_familia": "Camisetas",
    "cantidad": 2,
}


class CajaPendienteOut(BaseModel):
    """Una línea de caja pendiente (tabla `cajas_pendientes`), con claves
    normalizadas a snake_case."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": _CAJA_EXAMPLE},
    )

    cod_cliente: str | None = Field(None, description="Código de cliente (origen: CodCliente).")
    tienda: str | None = Field(None, description="Código de tienda (origen: Tienda).")
    nombre_tienda: str | None = Field(None, description="Nombre de la tienda (origen: NombreTienda).")
    dispatch_note: str | None = Field(None, description="Nº de albarán de envío (origen: DispathNote).")
    fecha_salida: str | None = Field(None, description="Fecha de salida (texto en origen: FechaSalida).")
    fecha_llegada: str | None = Field(None, description="Fecha de llegada (texto en origen: FechaLLegada).")
    codigo_caja: str | None = Field(None, description="Código de caja (origen: CodigoCaja).")
    no_bulto: str | None = Field(None, description="Nº de bulto (origen: NoBulto).")
    total_prendas: int | None = Field(None, description="Total de prendas de la caja (origen: TotalPrendas).")
    no_pedido: str | None = Field(None, description="Nº de pedido (origen: NoPedido).")
    no_envio: str | None = Field(None, description="Nº de envío (origen: NoEnvio).")
    ean: str | None = Field(None, description="Código de barras EAN (origen: EAN).")
    articulo: str | None = Field(None, description="Código de artículo (origen: Articulo).")
    color: str | None = Field(None, description="Código de color (origen: Color).")
    talla: str | None = Field(None, description="Talla (origen: Talla).")
    descripcion_articulo: str | None = Field(None, description="Descripción del artículo (origen: Descri_Art).")
    descripcion_color: str | None = Field(None, description="Descripción del color (origen: Descri_Color).")
    marca: str | None = Field(None, description="Marca (origen: Marca).")
    familia: str | None = Field(None, description="Código de familia (origen: Familia).")
    descripcion_familia: str | None = Field(None, description="Descripción de la familia (origen: Descri_Familia).")
    cantidad: int | None = Field(None, description="Cantidad en la línea (origen: Cantidad).")


class CajasPendientesPage(BaseModel):
    """Página de resultados de líneas de caja pendiente."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [_CAJA_EXAMPLE], "count": 1, "limit": 50, "offset": 0}
        }
    )

    items: list[CajaPendienteOut]
    count: int = Field(..., description="Nº de filas devueltas en esta página.")
    limit: int = Field(..., description="Tamaño de página solicitado.")
    offset: int = Field(..., description="Desplazamiento solicitado.")
