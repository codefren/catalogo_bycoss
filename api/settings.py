"""Configuración de la API, leída de variables de entorno (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+asyncpg://usuario:pass@postgres:5432/catalogo
    database_url: str

    # Orígenes permitidos para CORS, separados por coma (nunca "*" en prod).
    cors_origins: str = ""

    # Límite total de peticiones por IP, compartido por todos los endpoints (formato de slowapi).
    rate_limit: str = "1080/minute"

    # ── JWT ──────────────────────────────────────────────────────────────────
    # Secreto para firmar los tokens (HS256). OBLIGATORIO: sin él la API no
    # arranca. Genera uno fuerte con:  openssl rand -hex 32
    jwt_secret: str

    # Algoritmo de firma.
    jwt_algorithm: str = "HS256"

    # Caducidad del token de acceso, en horas.
    access_token_expire_hours: int = 12

    # Caducidad del refresh token, en días.
    refresh_token_expire_days: int = 7

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
