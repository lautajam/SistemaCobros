from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from werkzeug.security import check_password_hash

from .. import auth
from ..db import Session
from ..models import Usuario

bp = Blueprint("cuenta", __name__, url_prefix="/cuenta")


def _mostrar(error_clave=None, error_datos=None, estado=200, valores=None):
    return render_template(
        "cuenta/index.html", error_clave=error_clave, error_datos=error_datos,
        valores=valores or {}, obligatorio=current_user.debe_cambiar_password,
    ), estado


@bp.route("/")
def index():
    return _mostrar()


@bp.route("/clave", methods=["POST"])
def clave():
    """Cambia la contraseña del usuario que inició sesión (todos los roles)."""
    actual = request.form.get("actual") or ""
    nueva = request.form.get("nueva") or ""
    repetida = request.form.get("repetida") or ""

    if not check_password_hash(current_user.password_hash, actual):
        return _mostrar(error_clave="La contraseña actual no es correcta.", estado=400)
    if nueva != repetida:
        return _mostrar(error_clave="La contraseña nueva y su repetición no coinciden.", estado=400)
    if nueva == actual:
        return _mostrar(error_clave="La contraseña nueva tiene que ser distinta de la actual.", estado=400)
    problema = auth.validar_clave(nueva, current_user.usuario)
    if problema:
        return _mostrar(error_clave=problema, estado=400)

    usuario = Session.get(Usuario, current_user.id)
    usuario.password_hash = auth.hashear(nueva)
    usuario.debe_cambiar_password = False
    Session.commit()
    auth.cerrar_otras_sesiones(usuario)  # cierra las demás sesiones abiertas de este usuario
    flash("Contraseña actualizada.", "success")
    return redirect(url_for("main.index") if request.form.get("volver") == "inicio" else url_for("cuenta.index"))


@bp.route("/datos", methods=["POST"])
def datos():
    """Cambia el nombre y el usuario de la cuenta. Solo lo puede hacer el administrador."""
    if not current_user.es_admin:
        abort(403)
    nombre = (request.form.get("nombre") or "").strip()
    nombre_usuario = auth.normalizar_usuario(request.form.get("usuario"))
    valores = {"nombre": nombre, "usuario": nombre_usuario}

    problema = auth.validar_usuario(nombre_usuario)
    if not problema and not (2 <= len(nombre) <= 80):
        problema = "El nombre tiene que tener entre 2 y 80 caracteres."
    if not problema:
        otro = Session.scalar(select(Usuario).where(Usuario.usuario == nombre_usuario, Usuario.id != current_user.id))
        if otro:
            problema = "Ya existe otro usuario con ese nombre de usuario."
    if problema:
        return _mostrar(error_datos=problema, estado=400, valores=valores)

    usuario = Session.get(Usuario, current_user.id)
    usuario.nombre = nombre
    usuario.usuario = nombre_usuario
    Session.commit()
    flash("Datos de la cuenta actualizados.", "success")
    return redirect(url_for("cuenta.index"))
