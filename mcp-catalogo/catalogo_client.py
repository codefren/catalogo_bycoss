"""Cliente HTTP de solo lectura para la Catálogo API (bycos.data4tex.com).

Hace login con usuario/contraseña (variables de entorno), cachea el access token
y lo renueva con el refresh token de forma transparente: si una llamada devuelve
401, intenta refrescar y, si el refresh ya no vale, vuelve a hacer login, y
reintenta la petición una vez.

Variables de entorno:
  CATALOGO_BASE_URL  (opcional, por defecto https://bycos.data4tex.com)
  CATALOGO_USER      (obligatoria)
  CATALOGO_PASSWORD  (obligatoria)
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://bycos.data4tex.com"
PAGE_SIZE = 500  # tamaño de página máximo que admite la API


class CatalogoError(RuntimeError):
    """Error al hablar con la Catálogo API (credenciales, red o respuesta)."""


class CatalogoClient:
    """Cliente asíncrono con autenticación JWT gestionada."""

    def __init__(
        self,
        base_url: str | None = None,
        usuario: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("CATALOGO_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._usuario = usuario or os.getenv("CATALOGO_USER")
        self._password = password or os.getenv("CATALOGO_PASSWORD")
        if not self._usuario or not self._password:
            raise CatalogoError(
                "Faltan credenciales: define CATALOGO_USER y CATALOGO_PASSWORD "
                "(por ejemplo en mcp-catalogo/.env)."
            )
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self._access: str | None = None
        self._refresh: str | None = None
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── Autenticación ────────────────────────────────────────────────────────
    async def _login(self) -> None:
        resp = await self._client.post(
            "/auth/token",
            data={"username": self._usuario, "password": self._password},
        )
        if resp.status_code != 200:
            raise CatalogoError(
                f"Login falló ({resp.status_code}): revisa CATALOGO_USER / "
                f"CATALOGO_PASSWORD. Respuesta: {resp.text[:200]}"
            )
        data = resp.json()
        self._access = data["access_token"]
        self._refresh = data.get("refresh_token")

    async def _try_refresh(self) -> bool:
        if not self._refresh:
            return False
        resp = await self._client.post(
            "/auth/refresh", json={"refresh_token": self._refresh}
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        self._access = data["access_token"]
        # Rotación: el refresh usado queda revocado; guarda el nuevo.
        self._refresh = data.get("refresh_token", self._refresh)
        return True

    async def _ensure_token(self) -> None:
        if self._access is None:
            async with self._lock:
                if self._access is None:
                    await self._login()

    # ── Peticiones ───────────────────────────────────────────────────────────
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET contra la API con auth. Reintenta una vez si el token caducó."""
        await self._ensure_token()
        params = _limpiar(params)
        resp: httpx.Response | None = None
        for intento in range(2):
            headers = {"Authorization": f"Bearer {self._access}"}
            resp = await self._client.get(path, params=params, headers=headers)
            if resp.status_code != 401:
                break
            # Token caducado: renovar o volver a loguear, y reintentar una vez.
            async with self._lock:
                if not await self._try_refresh():
                    await self._login()
        assert resp is not None
        if resp.status_code == 404:
            raise CatalogoError(f"No encontrado: {path}")
        if resp.status_code >= 400:
            raise CatalogoError(
                f"Error {resp.status_code} en {path}: {resp.text[:300]}"
            )
        return resp.json()

    async def paginar(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_filas: int = PAGE_SIZE,
    ) -> list[dict]:
        """Recorre páginas (limit/offset) hasta `max_filas` o agotar resultados."""
        base = dict(_limpiar(params) or {})
        base["limit"] = PAGE_SIZE
        offset = int(base.get("offset", 0) or 0)
        filas: list[dict] = []
        while len(filas) < max_filas:
            base["offset"] = offset
            page = await self.get(path, base)
            items = page.get("items", []) if isinstance(page, dict) else []
            filas.extend(items)
            if page.get("count", 0) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return filas[:max_filas]


def _limpiar(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Quita las claves con valor None para no enviar filtros vacíos."""
    if not params:
        return params
    return {k: v for k, v in params.items() if v is not None}
