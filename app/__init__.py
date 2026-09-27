import os

from flask import Flask

from . import counters, db, settings


def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "service-tecnico-dev")
    app.config["BASE_DIR"] = base_dir
    app.config["DATABASE_URL"] = settings.database_url()
    # Un backup puede pesar bastante (incluye todos los PDF): sin límite práctico.
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

    # Plantillas de documentos (boleto.html / recibo.html), separadas del
    # motor de templates propio de Flask (app/templates, usado solo para la
    # interfaz web). Esto es lo que permite editarlas sin tocar el código.
    app.config["DOC_TEMPLATES_DIR"] = os.path.join(base_dir, "templates")
    app.config["DOCUMENTOS_DIR"] = os.path.join(base_dir, "documentos")

    db.init_db(app)
    _inicializar_carpetas(app)
    _registrar_blueprints(app)
    _registrar_context_processor(app)
    _registrar_modo_mantenimiento(app)

    return app


def _inicializar_carpetas(app):
    """Crea las carpetas de documentos si todavía no existen. El esquema de la
    base de datos lo crea Alembic (`alembic upgrade head`) al iniciar."""
    for carpeta in ("boletos", "recibos", os.path.join("blancos", "boletos"), os.path.join("blancos", "recibos")):
        os.makedirs(os.path.join(app.config["DOCUMENTOS_DIR"], carpeta), exist_ok=True)
    os.makedirs(app.config["DOC_TEMPLATES_DIR"], exist_ok=True)


def _registrar_blueprints(app):
    from .routes import backups, blancos, boletos, clientes, configuracion, historial, main, recibos

    app.register_blueprint(main.bp)
    app.register_blueprint(clientes.bp)
    app.register_blueprint(boletos.bp)
    app.register_blueprint(recibos.bp)
    app.register_blueprint(historial.bp)
    app.register_blueprint(configuracion.bp)
    app.register_blueprint(blancos.bp)
    app.register_blueprint(backups.bp)


def _registrar_context_processor(app):
    @app.context_processor
    def inject_globals():
        from .routes.configuracion import get_config

        return {
            "service_cfg": get_config(),
            "ultimo_boleto": counters.get_last_number("boleto"),
            "ultimo_recibo": counters.get_last_number("recibo"),
        }


def _registrar_modo_mantenimiento(app):
    @app.before_request
    def _bloquear_durante_restauracion():
        from . import backup

        if backup.RESTORING:
            return (
                "Se está restaurando un backup. Volvé a cargar la página en unos segundos.",
                503,
                {"Retry-After": "10"},
            )
