import os

from flask import Flask

from . import counters, csv_utils, models


def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "service-tecnico-dev")
    app.config["BASE_DIR"] = base_dir

    data_dir = os.path.join(base_dir, "data")
    app.config["CLIENTES_CSV"] = os.path.join(data_dir, "clientes", "clientes.csv")
    app.config["BOLETOS_CSV"] = os.path.join(data_dir, "boletos", "boletos.csv")
    app.config["RECIBOS_CSV"] = os.path.join(data_dir, "recibos", "recibos.csv")
    app.config["EQUIPOS_CSV"] = os.path.join(data_dir, "equipos", "equipos.csv")
    app.config["CONFIG_CSV"] = os.path.join(data_dir, "configuracion", "configuracion.csv")
    app.config["CONTADORES_CSV"] = os.path.join(data_dir, "configuracion", "contadores.csv")

    # Plantillas de documentos (boleto.html / recibo.html), separadas del
    # motor de templates propio de Flask (app/templates, usado solo para la
    # interfaz web). Esto es lo que permite editarlas sin tocar el código.
    app.config["DOC_TEMPLATES_DIR"] = os.path.join(base_dir, "templates")
    app.config["DOCUMENTOS_DIR"] = os.path.join(base_dir, "documentos")

    _inicializar_almacenamiento(app)
    _registrar_blueprints(app)
    _registrar_context_processor(app)

    return app


def _inicializar_almacenamiento(app):
    """Crea automáticamente todas las carpetas y CSV necesarios si todavía
    no existen (requisito: la app debe funcionar desde cero)."""
    csv_utils.ensure_csv(app.config["CLIENTES_CSV"], models.CLIENTE_FIELDS)
    csv_utils.ensure_csv(app.config["BOLETOS_CSV"], models.BOLETO_FIELDS)
    csv_utils.ensure_csv(app.config["RECIBOS_CSV"], models.RECIBO_FIELDS)
    csv_utils.ensure_csv(app.config["EQUIPOS_CSV"], models.EQUIPO_FIELDS)
    csv_utils.ensure_csv(app.config["CONFIG_CSV"], models.CONFIG_FIELDS)
    counters.ensure_counters(app.config["BASE_DIR"])

    for carpeta in ("boletos", "recibos", os.path.join("blancos", "boletos"), os.path.join("blancos", "recibos")):
        os.makedirs(os.path.join(app.config["DOCUMENTOS_DIR"], carpeta), exist_ok=True)
    os.makedirs(app.config["DOC_TEMPLATES_DIR"], exist_ok=True)


def _registrar_blueprints(app):
    from .routes import blancos, boletos, clientes, configuracion, historial, main, recibos

    app.register_blueprint(main.bp)
    app.register_blueprint(clientes.bp)
    app.register_blueprint(boletos.bp)
    app.register_blueprint(recibos.bp)
    app.register_blueprint(historial.bp)
    app.register_blueprint(configuracion.bp)
    app.register_blueprint(blancos.bp)


def _registrar_context_processor(app):
    @app.context_processor
    def inject_globals():
        from .routes.configuracion import get_config

        base_dir = app.config["BASE_DIR"]
        cfg = get_config(base_dir, app.config["CONFIG_CSV"])
        return {
            "service_cfg": cfg,
            "ultimo_boleto": counters.get_last_number(base_dir, "boleto"),
            "ultimo_recibo": counters.get_last_number(base_dir, "recibo"),
        }
