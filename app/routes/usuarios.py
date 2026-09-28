"""Gestión de usuarios (solo administrador): CRUD de técnicos y cambio de contraseña de cualquiera."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import delete, func, select

from .. import auth
from ..auth import ROL_ADMIN, ROL_TECNICO, permiso
from ..db import Session
from ..models import Boleto, IntentoLogin, Recibo, SesionActiva, Usuario

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

PERMISO = "usuarios:gestionar"


def _usuario_o_404(id_):
    usuario = Session.get(Usuario, id_)
    if usuario is None:
        abort(404)
    return usuario


def _tecnico_o_404(id_):
    usuario = _usuario_o_404(id_)
    if usuario.rol != ROL_TECNICO:
        abort(404)
    return usuario


def _validar_datos(nombre, nombre_usuario, ignorar_id=None):
    problema = auth.validar_usuario(nombre_usuario)
    if problema:
        return problema
    if not (2 <= len(nombre) <= 80):
        return "El nombre tiene que tener entre 2 y 80 caracteres."
    return auth.nombre_o_usuario_repetido(nombre, nombre_usuario, ignorar_id)


@bp.route("/")
@permiso(PERMISO)
def lista():
    usuarios = list(Session.scalars(select(Usuario).order_by(Usuario.rol, func.lower(Usuario.nombre))))
    return render_template("usuarios/lista.html", usuarios=usuarios)


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso(PERMISO)
def nuevo():
    valores = {"nombre": "", "usuario": ""}
    error = None
    if request.method == "POST":
        valores = {
            "nombre": auth.normalizar_nombre(request.form.get("nombre")),
            "usuario": auth.normalizar_usuario(request.form.get("usuario")),
        }
        clave = request.form.get("password") or ""
        error = _validar_datos(valores["nombre"], valores["usuario"]) or auth.validar_clave(clave, valores["usuario"])
        if not error:
            Session.add(Usuario(
                usuario=valores["usuario"], nombre=valores["nombre"], rol=ROL_TECNICO,
                password_hash=auth.hashear(clave), activo=True,
                debe_cambiar_password=True,  # siempre: la clave inicial la conoce el admin
            ))
            Session.commit()
            flash(f"Técnico «{valores['nombre']}» creado.", "success")
            return redirect(url_for("usuarios.lista"))
    return render_template("usuarios/form.html", tecnico=None, valores=valores, error=error), (400 if error else 200)


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@permiso(PERMISO)
def editar(usuario_id):
    tecnico = _tecnico_o_404(usuario_id)
    valores = {"nombre": tecnico.nombre, "usuario": tecnico.usuario}
    error = None
    if request.method == "POST":
        valores = {
            "nombre": auth.normalizar_nombre(request.form.get("nombre")),
            "usuario": auth.normalizar_usuario(request.form.get("usuario")),
        }
        error = _validar_datos(valores["nombre"], valores["usuario"], ignorar_id=tecnico.id)
        if not error:
            tecnico.nombre, tecnico.usuario = valores["nombre"], valores["usuario"]
            Session.commit()
            flash("Datos del técnico actualizados.", "success")
            return redirect(url_for("usuarios.lista"))
    return render_template("usuarios/form.html", tecnico=tecnico, valores=valores, error=error), (400 if error else 200)


@bp.route("/<int:usuario_id>/clave", methods=["GET", "POST"])
@permiso(PERMISO)
def clave(usuario_id):
    """El administrador define una contraseña nueva para otro usuario."""
    usuario = _usuario_o_404(usuario_id)
    if usuario.id == current_user.id:
        return redirect(url_for("cuenta.index"))  # la propia se cambia en "Mi cuenta"
    error = None
    if request.method == "POST":
        nueva = request.form.get("password") or ""
        error = auth.validar_clave(nueva, usuario.usuario)
        if not error:
            usuario.password_hash = auth.hashear(nueva)
            usuario.debe_cambiar_password = request.form.get("debe_cambiar") == "1"
            Session.execute(delete(SesionActiva).where(SesionActiva.usuario_id == usuario.id))  # cierra sus sesiones
            Session.execute(delete(IntentoLogin).where(IntentoLogin.usuario == usuario.usuario))
            Session.commit()
            flash(f"Contraseña de «{usuario.nombre_visible}» actualizada.", "success")
            return redirect(url_for("usuarios.lista"))
    return render_template("usuarios/clave.html", usuario=usuario, error=error), (400 if error else 200)


@bp.route("/<int:usuario_id>/estado", methods=["POST"])
@permiso(PERMISO)
def estado(usuario_id):
    """Activa o desactiva a un técnico (desactivado no puede ingresar; se conserva su historial)."""
    tecnico = _tecnico_o_404(usuario_id)
    tecnico.activo = not tecnico.activo
    if not tecnico.activo:
        Session.execute(delete(SesionActiva).where(SesionActiva.usuario_id == tecnico.id))
    Session.commit()
    flash(f"«{tecnico.nombre_visible}» {'activado' if tecnico.activo else 'desactivado'}.", "success")
    return redirect(url_for("usuarios.lista"))


@bp.route("/<int:usuario_id>/eliminar", methods=["POST"])
@permiso(PERMISO)
def eliminar(usuario_id):
    tecnico = _tecnico_o_404(usuario_id)
    boletos = Session.scalar(select(func.count()).select_from(Boleto).where(Boleto.creado_por_id == tecnico.id))
    recibos = Session.scalar(select(func.count()).select_from(Recibo).where(Recibo.creado_por_id == tecnico.id))
    if boletos or recibos:
        flash(
            f"No se puede eliminar a «{tecnico.nombre_visible}»: tiene {boletos} boleto(s) y {recibos} recibo(s) a su nombre. "
            "Desactivalo para que no pueda ingresar y conservar el historial.", "error",
        )
        return redirect(url_for("usuarios.lista"))
    Session.execute(delete(IntentoLogin).where(IntentoLogin.usuario == tecnico.usuario))
    Session.delete(tecnico)
    Session.commit()
    flash("Técnico eliminado.", "success")
    return redirect(url_for("usuarios.lista"))
