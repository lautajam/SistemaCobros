"""
auth.py
-------
Autenticación, roles y permisos.

- Todas las rutas exigen sesión iniciada (denegar por defecto), salvo las de
  ENDPOINTS_PUBLICOS. Los permisos por rol se aplican en el servidor con
  @permiso(...); ocultar botones en las plantillas es solo comodidad.
- Contraseñas: solo se guarda el hash (scrypt).
- Sesiones: cookie firmada; se invalidan al cambiar la contraseña.
- Login: bloqueo temporal por usuario y por IP tras varios intentos fallidos
  (se guardan en la base, así vale aunque haya varios procesos).
- CSRF: protección en todos los POST (Flask-WTF).
"""

import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlsplit

import click
from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_user, logout_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import delete, func, select, text
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .db import Session
from .models import IntentoLogin, SesionActiva, Usuario

log = logging.getLogger(__name__)

ROL_ADMIN = "admin"
ROL_TECNICO = "tecnico"
ROLES = {ROL_ADMIN: "Administrador", ROL_TECNICO: "Técnico"}

# "*" = todo. El técnico crea/ve/edita boletos y recibos, crea/ve clientes y
# ve el historial; no elimina, no edita clientes, no toca usuarios, la
# configuración ni los backups.
PERMISOS = {
    ROL_ADMIN: {"*"},
    ROL_TECNICO: {
        "clientes:ver", "clientes:crear",
        "boletos:ver", "boletos:crear",
        "recibos:ver", "recibos:crear",
        "historial:ver", "blancos:ver", "tarifario:ver",
    },
}

ENDPOINTS_PUBLICOS = {"auth.login", "static"}
# Con "debe cambiar la contraseña" pendiente solo se puede llegar a estos.
ENDPOINTS_CAMBIO_CLAVE = {"cuenta.index", "cuenta.clave", "cuenta.datos", "auth.logout", "static"}

MAX_INTENTOS_USUARIO = 5
MAX_INTENTOS_IP = 30
VENTANA_BLOQUEO = timedelta(minutes=5)
INACTIVIDAD_MAXIMA = timedelta(hours=12)

CLAVE_MINIMA = 8
CLAVES_TRIVIALES = {
    "admin", "administrador", "password", "contraseña", "contrasena", "12345678", "123456789",
    "1234567890", "qwertyui", "qwerty123", "abcd1234", "00000000", "11111111",
}
_RE_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")

login_manager = LoginManager()
csrf = CSRFProtect()

# Se compara contra este hash cuando el usuario no existe, para que tarde lo
# mismo que con un usuario real (no revelar qué usuarios existen).
_HASH_FALSO = generate_password_hash("contraseña-inexistente", method="scrypt")


# ------------------------------------------------------------------ permisos

def tiene_permiso(usuario, permiso):
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return False
    permitidos = PERMISOS.get(usuario.rol, set())
    return "*" in permitidos or permiso in permitidos


def permiso(nombre):
    """Decorador: exige un permiso; si falta responde 403."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not tiene_permiso(current_user, nombre):
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


# ---------------------------------------------------------------- contraseñas

def hashear(clave):
    return generate_password_hash(clave, method="scrypt")


def validar_clave(clave, usuario=""):
    """Devuelve un mensaje de error, o None si la contraseña es aceptable."""
    if len(clave) < CLAVE_MINIMA:
        return f"La contraseña debe tener al menos {CLAVE_MINIMA} caracteres."
    if len(clave) > 128:
        return "La contraseña es demasiado larga (máximo 128 caracteres)."
    if clave.lower() in CLAVES_TRIVIALES or (usuario and clave.lower() == usuario.lower()):
        return "Esa contraseña es demasiado fácil de adivinar. Elegí otra."
    return None


def normalizar_usuario(texto):
    return (texto or "").strip().lower()


def normalizar_nombre(texto):
    """Recorta y colapsa espacios repetidos ('Ana   Pérez ' -> 'Ana Pérez')."""
    return " ".join((texto or "").split())


def nombre_o_usuario_repetido(nombre, usuario, ignorar_id=None):
    """Mensaje de error si ya hay otro usuario con ese nombre de usuario o con ese nombre
    (sin distinguir mayúsculas), o None."""
    def otro(condicion):
        consulta = select(Usuario.id).where(condicion)
        if ignorar_id is not None:
            consulta = consulta.where(Usuario.id != ignorar_id)
        return Session.scalar(consulta) is not None

    if otro(Usuario.usuario == usuario):
        return "Ya existe un usuario con ese nombre de usuario."
    if otro(func.lower(Usuario.nombre) == nombre.lower()):
        return "Ya existe un usuario con ese nombre."
    return None


def validar_usuario(usuario):
    if not _RE_USUARIO.match(usuario):
        return "El usuario debe tener entre 3 y 30 caracteres: letras, números, punto, guion o guion bajo."
    return None


# --------------------------------------------------------------------- login

def _ahora():
    return datetime.now(timezone.utc)


def segundos_de_bloqueo(usuario, ip):
    """Segundos que faltan si este usuario o esta IP están bloqueados, o 0."""
    desde = _ahora() - VENTANA_BLOQUEO
    espera = 0
    for campo, valor, maximo in ((IntentoLogin.usuario, usuario, MAX_INTENTOS_USUARIO), (IntentoLogin.ip, ip, MAX_INTENTOS_IP)):
        if not valor:
            continue
        momentos = list(Session.scalars(
            select(IntentoLogin.momento).where(campo == valor, IntentoLogin.momento >= desde).order_by(IntentoLogin.momento.desc()).limit(maximo)
        ))
        if len(momentos) >= maximo:
            # Se libera cuando el intento más antiguo de la ventana deja de contar.
            espera = max(espera, int((momentos[-1] + VENTANA_BLOQUEO - _ahora()).total_seconds()) + 1)
    return max(espera, 0)


def registrar_fallo(usuario, ip):
    Session.add(IntentoLogin(usuario=usuario[:50], ip=(ip or "")[:64]))
    # Limpieza de intentos viejos.
    Session.execute(delete(IntentoLogin).where(IntentoLogin.momento < _ahora() - timedelta(days=1)))
    Session.commit()


def iniciar_sesion(usuario):
    session.clear()  # evita fijación de sesión
    login_user(usuario)
    token = secrets.token_hex(32)
    Session.execute(delete(SesionActiva).where(SesionActiva.ultimo_uso < _ahora() - INACTIVIDAD_MAXIMA))
    Session.add(SesionActiva(token=token, usuario_id=usuario.id))
    session["sid"] = token
    session.permanent = True
    usuario.ultimo_ingreso = _ahora()
    Session.execute(delete(IntentoLogin).where(IntentoLogin.usuario == usuario.usuario))
    Session.commit()


def cerrar_sesion_actual():
    token = session.get("sid")
    if token:
        Session.execute(delete(SesionActiva).where(SesionActiva.token == token))
        Session.commit()
    logout_user()
    session.clear()


def sesion_valida(usuario):
    """La sesión de la cookie tiene que existir en la base, ser de este usuario y no
    haber estado inactiva más de INACTIVIDAD_MAXIMA."""
    token = session.get("sid")
    if not token:
        return False
    fila = Session.get(SesionActiva, token)
    ahora = _ahora()
    if fila is None or fila.usuario_id != usuario.id or fila.ultimo_uso < ahora - INACTIVIDAD_MAXIMA:
        return False
    if ahora - fila.ultimo_uso > timedelta(seconds=60):  # no escribir en cada pedido
        fila.ultimo_uso = ahora
        Session.commit()
    return True


def cerrar_otras_sesiones(usuario, conservar_actual=True):
    """Invalida las sesiones abiertas del usuario (por ejemplo, al cambiar su clave)."""
    consulta = delete(SesionActiva).where(SesionActiva.usuario_id == usuario.id)
    if conservar_actual and session.get("sid"):
        consulta = consulta.where(SesionActiva.token != session["sid"])
    Session.execute(consulta)
    Session.commit()


def es_destino_seguro(destino):
    """Solo rutas internas ("/algo"): evita redirecciones a otros sitios."""
    if not destino or not destino.startswith("/") or destino.startswith("//") or "\\" in destino:
        return False
    partes = urlsplit(destino)
    return not partes.scheme and not partes.netloc


# ------------------------------------------------------------ admin inicial

def asegurar_admin_inicial():
    """Si no hay ningún usuario, crea el administrador inicial.

    - Desarrollo: admin / admin, con cambio de contraseña obligatorio en el
      primer ingreso (salvo que se definan ADMIN_USUARIO / ADMIN_PASSWORD).
    - Producción (APP_ENV=production): NUNCA crea admin/admin; exige
      ADMIN_PASSWORD. Sin eso, no crea nada (se usa `flask reset-admin`).
    """
    try:
        if Session.scalar(select(func.count()).select_from(Usuario)):
            return None
    except Exception:
        Session.rollback()
        log.warning("No se pudo consultar la tabla de usuarios (¿faltan las migraciones?).")
        return None

    produccion = current_app.config["APP_ENV"] == "production"
    nombre_usuario = normalizar_usuario(os.environ.get("ADMIN_USUARIO", "admin")) or "admin"
    clave = os.environ.get("ADMIN_PASSWORD", "")

    if produccion and not clave:
        log.warning(
            "No hay usuarios y APP_ENV=production: no se crea el admin por defecto. "
            "Definí ADMIN_PASSWORD o ejecutá: docker compose exec app flask --app run reset-admin"
        )
        return None
    if clave:
        problema = validar_clave(clave, nombre_usuario)
        if problema:
            log.error("ADMIN_PASSWORD no es válida (%s). No se creó el administrador.", problema)
            return None
        forzar_cambio = False
    else:
        clave, forzar_cambio = "admin", True

    admin = Usuario(
        usuario=nombre_usuario, nombre="Administrador", rol=ROL_ADMIN, password_hash=hashear(clave),
        activo=True, debe_cambiar_password=forzar_cambio,
    )
    Session.add(admin)
    try:
        Session.commit()
    except Exception:  # otro proceso lo creó al mismo tiempo
        Session.rollback()
        return None
    log.info("Administrador inicial creado: %s%s", nombre_usuario, " (debe cambiar la contraseña)" if forzar_cambio else "")
    return admin


def obtener_secret_key(app):
    """Clave que firma las sesiones. En producción es obligatoria (variable
    SECRET_KEY). En desarrollo, si no se define, se genera una al azar la
    primera vez y se guarda en la base."""
    clave = os.environ.get("SECRET_KEY", "").strip()
    if clave and clave != "service-tecnico-dev":
        return clave
    if app.config["APP_ENV"] == "production":
        raise RuntimeError(
            "Falta la variable SECRET_KEY (obligatoria con APP_ENV=production). "
            "Generá una con: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    try:
        with db.get_engine().begin() as conexion:
            conexion.execute(
                text("INSERT INTO ajustes (clave, valor) VALUES ('secret_key', :v) ON CONFLICT (clave) DO NOTHING"),
                {"v": secrets.token_hex(32)},
            )
            return conexion.execute(text("SELECT valor FROM ajustes WHERE clave = 'secret_key'")).scalar_one()
    except Exception:
        log.warning("No se pudo guardar la clave secreta en la base; se usa una temporal (las sesiones se pierden al reiniciar).")
        return secrets.token_hex(32)


# --------------------------------------------------------------- integración

def _es_api():
    return request.path.startswith("/clientes/api/") or request.accept_mimetypes.best == "application/json"


def _no_autenticado():
    if _es_api():
        return jsonify({"error": "Tenés que iniciar sesión."}), 401
    return redirect(url_for("auth.login"))


def init_app(app):
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)  # el token vale mientras dure la sesión
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.session_protection = "basic"
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def cargar_usuario(identificador):
        try:
            usuario = Session.get(Usuario, int(identificador))
        except (TypeError, ValueError):
            return None
        return usuario if usuario is not None and usuario.activo else None

    login_manager.unauthorized_handler(_no_autenticado)

    @app.before_request
    def _control_de_acceso():
        endpoint = request.endpoint
        if endpoint is None or endpoint in ENDPOINTS_PUBLICOS:
            return None
        if not current_user.is_authenticated:
            return _no_autenticado()
        # La sesión tiene que seguir registrada en la base (cerrar sesión, cambiar la
        # clave o desactivar al usuario la invalidan aunque la cookie siga existiendo).
        if not sesion_valida(current_user):
            logout_user()
            session.clear()
            flash("Tu sesión terminó. Volvé a ingresar.", "warning")
            return _no_autenticado()
        if current_user.debe_cambiar_password and endpoint not in ENDPOINTS_CAMBIO_CLAVE:
            if _es_api():
                return jsonify({"error": "Tenés que cambiar tu contraseña primero."}), 403
            return redirect(url_for("cuenta.index"))
        return None

    @app.after_request
    def _cabeceras_de_seguridad(respuesta):
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "DENY")
        respuesta.headers.setdefault("Referrer-Policy", "same-origin")
        respuesta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.is_secure:
            respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if respuesta.mimetype == "text/html":
            respuesta.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            )
        if current_user.is_authenticated and respuesta.mimetype == "text/html":
            respuesta.headers["Cache-Control"] = "no-store"  # no dejar páginas con datos en la caché
        return respuesta

    def _pagina_de_error(codigo, titulo, mensaje):
        if _es_api():
            return jsonify({"error": mensaje}), codigo
        return render_template("errors/error.html", codigo=codigo, titulo=titulo, mensaje=mensaje), codigo

    @app.errorhandler(403)
    def _prohibido(_e):
        return _pagina_de_error(403, "Sin permiso", "Tu usuario no tiene permiso para hacer esto. Si lo necesitás, pedíselo a un administrador.")

    @app.errorhandler(404)
    def _no_encontrado(_e):
        return _pagina_de_error(404, "No encontrado", "La página que buscás no existe o fue eliminada.")

    @app.errorhandler(CSRFError)
    def _csrf(_e):
        if _es_api():
            return jsonify({"error": "La sesión venció. Recargá la página e intentá de nuevo."}), 400
        flash("La página estuvo abierta demasiado tiempo o la sesión venció. Intentá de nuevo.", "warning")
        ruta = urlsplit(request.referrer or "").path
        return redirect(ruta if es_destino_seguro(ruta) else url_for("main.index"))

    @app.context_processor
    def _permisos_en_plantillas():
        return {"puede": lambda nombre: tiene_permiso(current_user, nombre), "ROLES": ROLES}

    @app.cli.command("reset-admin")
    @click.option("--usuario", default="admin", show_default=True, help="Usuario administrador a crear o recuperar.")
    def reset_admin(usuario):
        """Crea un administrador o le restablece la contraseña (recuperación de acceso)."""
        nombre_usuario = normalizar_usuario(usuario)
        problema = validar_usuario(nombre_usuario)
        if problema:
            raise click.ClickException(problema)
        clave = click.prompt("Nueva contraseña", hide_input=True, confirmation_prompt=True)
        problema = validar_clave(clave, nombre_usuario)
        if problema:
            raise click.ClickException(problema)
        existente = Session.scalar(select(Usuario).where(Usuario.usuario == nombre_usuario))
        if existente:
            existente.rol, existente.activo = ROL_ADMIN, True
            existente.password_hash = hashear(clave)
            existente.debe_cambiar_password = False
            Session.execute(delete(SesionActiva).where(SesionActiva.usuario_id == existente.id))
            accion = "actualizado"
        else:
            Session.add(Usuario(
                usuario=nombre_usuario, nombre="Administrador", rol=ROL_ADMIN, password_hash=hashear(clave),
                activo=True, debe_cambiar_password=False,
            ))
            accion = "creado"
        Session.execute(delete(IntentoLogin))
        Session.commit()
        click.echo(f"Administrador '{nombre_usuario}' {accion}. Ya podés ingresar con la nueva contraseña.")
