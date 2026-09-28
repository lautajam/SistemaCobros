import logging
import os
from datetime import timedelta

from flask import Flask
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, categorias_trabajo, counters, db, fechas, formatos, models, settings, tipos

log = logging.getLogger(__name__)


def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__)
    app.config["BASE_DIR"] = base_dir
    app.config["DATABASE_URL"] = settings.database_url()
    # Un backup puede pesar bastante (incluye todos los PDF): sin límite práctico.
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

    # "production" endurece el arranque: SECRET_KEY obligatoria, cookies solo
    # por HTTPS y nunca se crea el admin por defecto (admin/admin).
    app.config["APP_ENV"] = os.environ.get("APP_ENV", "development").strip().lower()
    produccion = app.config["APP_ENV"] == "production"

    # Sesiones: cookie firmada, no accesible desde JavaScript, que vence tras 12 h sin uso.
    valor_cookie = os.environ.get("COOKIE_SECURE", "").strip()
    cookie_segura = (valor_cookie == "1") if valor_cookie else produccion
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=cookie_segura,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        SESSION_REFRESH_EACH_REQUEST=True,
    )

    # Detrás de un proxy inverso (Caddy, nginx...) hay que confiar en sus cabeceras
    # X-Forwarded-* para conocer la IP y el esquema (https) reales del visitante.
    proxies = int(os.environ.get("TRUSTED_PROXIES", "0") or 0)
    if proxies > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)

    # Plantillas de documentos (boleto.html / recibo.html), separadas del
    # motor de templates propio de Flask (app/templates, usado solo para la
    # interfaz web). Esto es lo que permite editarlas sin tocar el código.
    app.config["DOC_TEMPLATES_DIR"] = os.path.join(base_dir, "templates")
    app.config["DOCUMENTOS_DIR"] = os.path.join(base_dir, "documentos")

    db.init_db(app)
    app.config["SECRET_KEY"] = auth.obtener_secret_key(app)
    _inicializar_carpetas(app)
    _registrar_modo_mantenimiento(app)  # antes que el control de acceso
    auth.init_app(app)
    _registrar_blueprints(app)
    _registrar_filtros(app)
    _registrar_context_processor(app)

    with app.app_context():
        auth.asegurar_admin_inicial()

    return app


def _inicializar_carpetas(app):
    """Crea las carpetas de documentos si todavía no existen. El esquema de la
    base de datos lo crea Alembic (`alembic upgrade head`) al iniciar."""
    for carpeta in ("boletos", "recibos", "tarifario", os.path.join("blancos", "boletos"), os.path.join("blancos", "recibos")):
        os.makedirs(os.path.join(app.config["DOCUMENTOS_DIR"], carpeta), exist_ok=True)
    os.makedirs(app.config["DOC_TEMPLATES_DIR"], exist_ok=True)


def _registrar_blueprints(app):
    from .routes import (
        auditoria as rutas_auditoria, auth as rutas_auth, backups, blancos, boletos, clientes, configuracion, cuenta, historial, main,
        recibos, tarifario, tipos as rutas_tipos, usuarios,
    )

    app.register_blueprint(rutas_auth.bp)
    app.register_blueprint(cuenta.bp)
    app.register_blueprint(usuarios.bp)
    app.register_blueprint(rutas_tipos.bp)
    app.register_blueprint(rutas_auditoria.bp)
    app.register_blueprint(tarifario.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(clientes.bp)
    app.register_blueprint(boletos.bp)
    app.register_blueprint(recibos.bp)
    app.register_blueprint(historial.bp)
    app.register_blueprint(configuracion.bp)
    app.register_blueprint(blancos.bp)
    app.register_blueprint(backups.bp)


def _registrar_filtros(app):
    @app.template_filter("pesos")
    def pesos(valor):
        """45000.5 -> '45.000,50' (formato argentino). Vacío -> '0,00'."""
        return formatos.pesos(valor)

    @app.template_filter("fecha")
    def fecha(valor):
        """2026-09-27 -> 27/09/2026 (formato de fecha de toda la interfaz)."""
        return fechas.a_texto(valor)

    app.jinja_env.globals["tipos_equipo"] = tipos.nombres
    app.jinja_env.globals["categorias_trabajo"] = categorias_trabajo.nombres

    @app.template_filter("fecha_hora")
    def fecha_hora(valor):
        """Fecha y hora local (zona horaria del contenedor) para mostrar."""
        if not valor:
            return "—"
        return valor.astimezone().strftime("%d/%m/%Y %H:%M")


def _registrar_context_processor(app):
    @app.context_processor
    def inject_globals():
        from .routes.configuracion import get_config

        estaticos = os.path.join(app.root_path, "static")
        version = max(
            int(os.path.getmtime(os.path.join(carpeta, archivo)))
            for carpeta in (os.path.join(estaticos, "css"), os.path.join(estaticos, "js"))
            for archivo in os.listdir(carpeta)
        )
        datos = {"asset_v": version, "service_cfg": get_config(), "COMPLEJIDADES": models.COMPLEJIDADES}
        if current_user.is_authenticated:
            datos["ultimo_boleto"] = counters.get_last_number("boleto")
            datos["ultimo_recibo"] = counters.get_last_number("recibo")
        return datos


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
