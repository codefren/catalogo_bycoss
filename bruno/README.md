# Colección Bruno — Catálogo API

Colección de [Bruno](https://www.usebruno.com/) con todas las peticiones de la API,
tests básicos y entornos `local` y `produccion`.

## Configuración

```bash
cp bruno/.env.example bruno/.env   # pon usuario y contraseña (no se sube a git)
```

En Bruno: **Open Collection** → carpeta `bruno/` → elige el entorno arriba a la derecha.

## Uso

1. **01 Auth / Login** guarda `accessToken` y `refreshToken`; el resto de peticiones
   heredan el Bearer de la colección.
2. Los listados guardan ejemplos (`skuEjemplo`, clave de ticket, `cajaEjemplo`) que
   usan las peticiones de detalle. Ejecútalas en orden o con **Run collection**.
3. Los filtros opcionales están desactivados en la pestaña *Params*; actívalos para probarlos.

Valores de ejemplo (`articulo`, `almacen`, `fechaDesde`, `fechaHasta`) en
`environments/*.bru`.

## Desde la terminal

```bash
npm i -g @usebruno/cli
cd bruno
bru run --env produccion            # toda la colección, con tests
bru run "02 SKU" --env produccion   # solo una carpeta
```

En `local` la URL es `http://localhost:8000`; el compose no publica ese puerto por
defecto (descomenta `ports` en el servicio `api`) o sobrescríbela con
`--env-var baseUrl=http://...`.
