"""Configuración leída del entorno (variables definidas en docker-compose.yml)."""

import os

DEFAULT_DATABASE_URL = "postgresql+psycopg://service_app:changeme@localhost:5432/service_app"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
