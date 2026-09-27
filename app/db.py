"""
db.py
-----
Conexión a PostgreSQL con SQLAlchemy. Una sesión por hilo (scoped_session),
que se cierra sola al terminar cada pedido de Flask.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

Session = scoped_session(sessionmaker(autoflush=False, expire_on_commit=False))
_engine = None


def init_db(app):
    global _engine
    _engine = create_engine(app.config["DATABASE_URL"], pool_pre_ping=True)
    Session.configure(bind=_engine)

    @app.teardown_appcontext
    def _cerrar_sesion(_exc):
        Session.remove()


def get_engine():
    return _engine


def dispose():
    """Cierra todas las conexiones abiertas (se usa antes de restaurar un
    backup, para que nadie mantenga tablas bloqueadas)."""
    Session.remove()
    if _engine is not None:
        _engine.dispose()
