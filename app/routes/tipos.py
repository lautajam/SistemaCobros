"""Tipos de equipo (solo administrador): alta, cambio de nombre, deshabilitar y eliminar.

Boletos y recibos guardan el nombre del tipo escrito en el propio documento, así que
deshabilitar, renombrar o eliminar un tipo NO toca los documentos ya emitidos."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from .. import tipos as logica
from ..auth import permiso
from ..db import Session
from ..models import Boleto, Recibo, TipoEquipo

bp = Blueprint("tipos", __name__, url_prefix="/tipos-equipo")

PERMISO = "tipos:gestionar"


def _en_uso(nombre):
    boletos = Session.scalar(select(func.count()).select_from(Boleto).where(Boleto.equipo == nombre))
    recibos = Session.scalar(select(func.count()).select_from(Recibo).where(Recibo.equipo == nombre))
    return boletos, recibos


def _validar_nombre(nombre, ignorar_id=None):
    if not (2 <= len(nombre) <= 60):
        return "El nombre tiene que tener entre 2 y 60 caracteres."
    consulta = select(TipoEquipo).where(func.lower(TipoEquipo.nombre) == nombre.lower())
    if ignorar_id is not None:
        consulta = consulta.where(TipoEquipo.id != ignorar_id)
    if Session.scalar(consulta):
        return "Ya existe un tipo de equipo con ese nombre."
    return None


@bp.route("/", methods=["GET", "POST"])
@permiso(PERMISO)
def lista():
    error, nombre_nuevo = None, ""
    if request.method == "POST":
        nombre_nuevo = logica.normalizar(request.form.get("nombre"))
        error = _validar_nombre(nombre_nuevo)
        if not error:
            Session.add(TipoEquipo(nombre=nombre_nuevo, activo=True))
            Session.commit()
            flash(f"Tipo «{nombre_nuevo}» agregado.", "success")
            return redirect(url_for("tipos.lista"))
    filas = []
    for tipo in Session.scalars(select(TipoEquipo).order_by(func.lower(TipoEquipo.nombre))):
        boletos, recibos = _en_uso(tipo.nombre)
        filas.append({"id": tipo.id, "nombre": tipo.nombre, "activo": tipo.activo, "boletos": boletos, "recibos": recibos})
    return render_template("tipos/lista.html", tipos=filas, error=error, nombre_nuevo=nombre_nuevo), (400 if error else 200)


@bp.route("/<int:tipo_id>/editar", methods=["GET", "POST"])
@permiso(PERMISO)
def editar(tipo_id):
    tipo = Session.get(TipoEquipo, tipo_id)
    if tipo is None:
        abort(404)
    error, nombre = None, tipo.nombre
    if request.method == "POST":
        nombre = logica.normalizar(request.form.get("nombre"))
        error = _validar_nombre(nombre, ignorar_id=tipo.id)
        if not error:
            tipo.nombre = nombre  # los documentos ya emitidos conservan el nombre que tenían
            Session.commit()
            flash("Tipo de equipo actualizado.", "success")
            return redirect(url_for("tipos.lista"))
    return render_template("tipos/form.html", tipo=tipo, nombre=nombre, error=error), (400 if error else 200)


@bp.route("/<int:tipo_id>/estado", methods=["POST"])
@permiso(PERMISO)
def estado(tipo_id):
    tipo = Session.get(TipoEquipo, tipo_id)
    if tipo is None:
        abort(404)
    tipo.activo = not tipo.activo
    Session.commit()
    if tipo.activo:
        flash(f"Tipo «{tipo.nombre}» habilitado: vuelve a aparecer al crear boletos y recibos.", "success")
    else:
        flash(f"Tipo «{tipo.nombre}» deshabilitado: ya no se ofrece en boletos y recibos nuevos. Los ya emitidos no cambian.", "success")
    return redirect(url_for("tipos.lista"))


@bp.route("/<int:tipo_id>/eliminar", methods=["POST"])
@permiso(PERMISO)
def eliminar(tipo_id):
    tipo = Session.get(TipoEquipo, tipo_id)
    if tipo is None:
        abort(404)
    nombre = tipo.nombre
    Session.delete(tipo)
    Session.commit()
    flash(f"Tipo «{nombre}» eliminado. Los boletos y recibos ya emitidos conservan su nombre.", "success")
    return redirect(url_for("tipos.lista"))
