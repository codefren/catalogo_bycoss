"""Conexiones a SQL Server (origen) y PostgreSQL (destino).

Credenciales por variables de entorno (ver .env.example). Nada hardcodeado.
"""
from __future__ import annotations

import os

import psycopg2
import pymssql


def mssql_conn():
    """Conexión al SQL Server de origen (Arsys).

    tds_version 7.0 por defecto: el SQL Server de Arsys tiene un certificado
    autofirmado y FreeTDS no completa el handshake con cifrado (TDS 7.2+); 7.0
    conecta sin cifrado, como hacía el JDBC con trustServerCertificate. Se puede
    cambiar con TDS_VERSION si el servidor lo permite.
    """
    return pymssql.connect(
        server=os.environ["SQLSERVER_HOST"],
        port=int(os.getenv("SQLSERVER_PORT", "1433")),
        user=os.environ["SQLSERVER_USER"],
        password=os.environ["SQLSERVER_PASSWORD"],
        database=os.environ["SQLSERVER_DB"],
        tds_version=os.getenv("TDS_VERSION", "7.0"),
        login_timeout=30,
        timeout=0,  # sin límite de query (tablas grandes)
    )


def pg_conn():
    """Conexión al PostgreSQL de destino (catálogo)."""
    return psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.environ["PG_DATABASE"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
    )
