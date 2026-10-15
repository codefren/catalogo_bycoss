"""Configuración de la API, leída de variables de entorno (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+asyncpg://usuario:pass@postgres:5432/catalogo
    database_url: str

    # Claves de API válidas, separadas por coma. Cada tercero usa la suya.
    api_keys: str = ""

    # Orígenes permitidos para CORS, separados por coma (nunca "*" en prod).
    cors_origins: str = ""

    # Límite de peticiones por clave/IP (formato de slowapi).
    rate_limit: str = "60/minute"

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
