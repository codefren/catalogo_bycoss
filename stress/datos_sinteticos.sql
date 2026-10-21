-- Datos sintéticos para pruebas de carga EN LOCAL (nunca en producción).
-- Volumen: sku 250k, ticket_maestro 500k líneas (~200k tickets, ene-2024 a
-- oct-2025), compras_maestro 100k, cajas_pendientes 20k.
-- Las tablas replican las columnas que usa la API (tipos del origen).

CREATE TABLE sku (
    sku text, "fldIdAlmacen" text, "fldIdArticulo" text, articulo_descripcion text,
    "fldTemporada" text, "fldIdFamilia" text, "fldIdProveedor" text, "fldReferencia" text,
    codigo_barras text, "fldColeccion" text, "fldMinimoStock" double precision,
    "fldMaximoStock" double precision, "fldPuntoPedido" double precision, "fldIdMarca" text,
    "fldIdSexo" text, "fldIdGrupo" text, "fldIdSubgrupo" text, "fldIdSubfamilia" text,
    "fldidTemporadaVenta" text, "fldIdColor" text, color_descripcion text,
    "fldIdGrupoTallas" text, grupotalla_descripcion text, talla text, pvp double precision,
    precio_costo double precision, total_entradas double precision,
    total_salidas double precision, total_servicio double precision,
    total_transito double precision, stock_disponible double precision,
    actualizado_en timestamp without time zone NOT NULL
);

-- 5.000 artículos × 5 colores × 5 tallas × 2 almacenes = 250.000 filas.
INSERT INTO sku (sku, "fldIdAlmacen", "fldIdArticulo", articulo_descripcion, "fldTemporada",
                 "fldIdFamilia", "fldIdProveedor", "fldReferencia", codigo_barras, "fldColeccion",
                 "fldIdMarca", "fldIdColor", color_descripcion, "fldIdGrupoTallas",
                 grupotalla_descripcion, talla, pvp, precio_costo, stock_disponible, actualizado_en)
SELECT
    lpad(a::text, 10, '0') || '-' || lpad(c::text, 6, '0') || '-' || t,
    lpad((200 + al)::text, 8, '0'),
    lpad(a::text, 10, '0'),
    (ARRAY['Camiseta', 'Pantalón', 'Vestido', 'Chaqueta', 'Falda', 'Camisa', 'Jersey', 'Bolso'])[1 + a % 8]
        || ' modelo ' || a,
    (ARRAY['V24', 'I24', 'V25', 'I25'])[1 + a % 4],
    (ARRAY['CAM', 'PAN', 'VES', 'CHA', 'FAL', 'CMS', 'JER', 'COM'])[1 + a % 8],
    'PROV' || (a % 50),
    'REF-' || a,
    '84' || lpad((a * 100 + c * 10 + ascii(t) % 10)::text, 11, '0'),
    'Colección ' || (a % 10),
    'BYC',
    lpad(c::text, 6, '0'),
    'Color ' || c,
    'GT1',
    'Tallas S-XL',
    t,
    round((10 + random() * 90)::numeric, 2),
    round((3 + random() * 30)::numeric, 2),
    floor(random() * 10),
    timestamp '2025-01-01' + random() * interval '290 days'
FROM generate_series(1, 5000) a,
     generate_series(1, 5) c,
     unnest(ARRAY['S', 'M', 'L', 'XL', 'U']) t,
     generate_series(7, 8) al;

CREATE TABLE ticket_maestro (
    "fldIdEmpresa" text, "fldIdAlmacen" text, "fldIdCaja" text, "fldIdTicket" text,
    "fldLinea" text, fecha date, "fldHora" text, "fldIdCliente" text, "fldIdMoneda" text,
    "fldCambio" double precision, "fldIdArticulo" text, "fldIdColor" text, "fldTalla" text,
    sku text, "fldCantidad" double precision, "fldPrecio" double precision,
    dto_linea double precision, importe_linea double precision, "fldIVA" double precision,
    actualizado_en timestamp, "fldPrendas" double precision, "fldImporteBruto" double precision,
    "fldImporteDto" double precision, "fldImporteNeto" double precision,
    "fldCobradoTicket" double precision, "fldPteTicket" double precision,
    dto_cabecera double precision, "fldVales" integer, "fldApartados" integer,
    "fldArreglos" integer, "fldPromociones" integer, "fldChequeRegalo" integer,
    "fldCupones" double precision, "fldEspecial" double precision
);

-- ~200k tickets con 1-4 líneas (≈ 500k líneas), 20 tiendas, 3 cajas.
INSERT INTO ticket_maestro
SELECT
    '0001',
    lpad((200 + tk % 20)::text, 8, '0'),
    lpad((1 + tk % 3)::text, 6, '0'),
    tk::text,
    lpad(l::text, 4, '0'),
    date '2024-01-01' + (tk % 660),
    '12:00:00', lpad((tk % 5000)::text, 8, '0'), 'EUR', 1,
    lpad((1 + (tk * l) % 5000)::text, 10, '0'), '000001', 'M',
    lpad((1 + (tk * l) % 5000)::text, 10, '0') || '-000001-M',
    1, 29.95, 0, 29.95, 21, now(),
    n, 29.95 * n, 0, 29.95 * n, 29.95 * n, 0, 0, 0, 0, 0, 0, 0, 0, 0
FROM (SELECT tk, 1 + (tk * 7) % 4 AS n FROM generate_series(1, 200000) tk) t,
     LATERAL generate_series(1, t.n) l;

CREATE TABLE compras_maestro (
    "fldIdEmpresa" text, "fldIdAlmacen" text, "fldIdProveedor" text, nombre_proveedor text,
    fecha date, "fldIdArticulo" text, "fldIdColor" text, talla_pos integer, talla text,
    cantidad double precision, acumulado double precision, "fldIdMoneda" text,
    "fldCambio" double precision, descripcion_articulo text, "fldTemporada" text,
    "fldIdFamilia" text, "fldIdGrupoTallas" text, descripcion_grupo_tallas text
);

INSERT INTO compras_maestro
SELECT '0001', lpad((200 + i % 20)::text, 8, '0'), 'PROV' || (i % 50), 'Proveedor ' || (i % 50),
       date '2024-01-01' + (i % 660), lpad((1 + i % 5000)::text, 10, '0'), '000001',
       1 + i % 5, 'M', 12, 12, 'EUR', 1, 'Artículo ' || i, 'V25', 'CAM', 'GT1', 'Tallas S-XL'
FROM generate_series(1, 100000) i;

CREATE TABLE cajas_pendientes (
    "CodCliente" text, "Tienda" text, "NombreTienda" text, "DispathNote" text,
    "FechaSalida" text, "FechaLLegada" text, "CodigoCaja" text, "NoBulto" text,
    "TotalPrendas" text, "NoPedido" text, "NoEnvio" text, "EAN" text, "Articulo" text,
    "Color" text, "Talla" text, "Descri_Art" text, "Descri_Color" text, "Marca" text,
    "Familia" text, "Descri_Familia" text, "Cantidad" text
);

INSERT INTO cajas_pendientes
SELECT 'C1', lpad((200 + i % 20)::text, 8, '0'), 'Tienda ' || (i % 20), 'DN-' || (i / 20),
       to_char(date '2025-09-01' + (i % 50), 'YYYY-MM-DD'), to_char(date '2025-09-05' + (i % 50), 'YYYY-MM-DD'),
       'CJ' || (i / 10), '1/1', '10', 'PED-' || (i / 30), 'ENV-' || (i / 40), '84' || lpad(i::text, 11, '0'),
       lpad((1 + i % 5000)::text, 10, '0'), '000001', 'M', 'Artículo', 'Color', 'BYC', 'CAM', 'Camisetas', '1'
FROM generate_series(1, 20000) i;

ANALYZE;
