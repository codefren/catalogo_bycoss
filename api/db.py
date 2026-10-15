"""Motor async de SQLAlchemy hacia Postgres.

Usamos SQLAlchemy Core con sentencias parametrizadas (bind params): nunca se
concatena input del usuario en el SQL, así que no hay inyección.
"""
from sqlalchemy.ext.asyncio import create_async_engine

from settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # evita conexiones muertas tras inactividad
)
