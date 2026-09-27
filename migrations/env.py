"""Entorno de Alembic. La URL de la base sale de DATABASE_URL (ver app/settings.py).

No se configura el logging de Alembic a propósito: este archivo también se
ejecuta dentro de la app (al restaurar un backup) y no debe pisar su logging.
"""

from alembic import context
from sqlalchemy import create_engine, pool

from app import settings
from app.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=settings.database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(settings.database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
