from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import Integer, cast, delete, func, or_, select

from .. import counters, models, repo
from ..auth import permiso
from ..db import Session
from ..models import Boleto, Cliente, Equipo, Recibo

bp = Blueprint("clientes", __name__, url_prefix="/clientes")


def _campos_desde(formulario):
    return {
        "nombre": (formulario.get("nombre") or "").strip(),
        "dni_cuit": (formulario.get("dni_cuit") or "").strip(),
        "telefono": (formulario.get("telefono") or "").strip(),
        "email": (formulario.get("email") or "").strip(),
        "direccion": (formulario.get("direccion") or "").strip(),
        "localidad": (formulario.get("localidad") or "").strip(),
        "codigo_postal": (formulario.get("codigo_postal") or "").strip(),
        "observaciones": (formulario.get("observaciones") or "").strip(),
    }


def _criterio_busqueda(q, incluir_email):
    campos = [Cliente.nombre, Cliente.dni_cuit, Cliente.telefono]
    if incluir_email:
        campos.append(Cliente.email)
    return or_(*[campo.icontains(q, autoescape=True) for campo in campos])


def crear_cliente(formulario) -> dict:
    """Crea un cliente nuevo con ID interno único y permanente (nunca el
    nombre). Usado tanto por el formulario propio de clientes como por el
    botón 'Nuevo cliente' dentro de boletos/recibos."""
    numero = counters.next_number("cliente")
    cliente = {"id": models.format_cliente_id(numero), **_campos_desde(formulario)}
    return repo.insertar(Cliente, cliente)


@bp.route("/")
@permiso("clientes:ver")
def lista():
    q = (request.args.get("q") or "").strip()
    criterios = [_criterio_busqueda(q, incluir_email=True)] if q else []
    clientes = repo.listar(Cliente, *criterios, order_by=[func.lower(Cliente.nombre)])
    return render_template("clientes/lista.html", clientes=clientes, q=request.args.get("q", ""))


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso("clientes:crear")
def nuevo():
    if request.method == "POST":
        cliente = crear_cliente(request.form)
        return redirect(url_for("clientes.detalle", cliente_id=cliente["id"]))
    return render_template("clientes/form.html", cliente=None)


@bp.route("/api/crear-rapido", methods=["POST"])
@permiso("clientes:crear")
def crear_rapido():
    """Endpoint AJAX: crea un cliente sin recargar la página (usado desde el
    formulario de boleto/recibo)."""
    datos = request.get_json(force=True, silent=True) or {}
    if not (datos.get("nombre") or "").strip():
        return jsonify({"error": "El nombre es obligatorio."}), 400
    cliente = crear_cliente(datos)
    return jsonify(cliente)


@bp.route("/api/buscar")
@permiso("clientes:ver")
def api_buscar():
    q = (request.args.get("q") or "").strip()
    criterios = [_criterio_busqueda(q, incluir_email=False)] if q else []
    clientes = repo.listar(Cliente, *criterios, order_by=[func.lower(Cliente.nombre)])
    return jsonify(clientes[:25])


@bp.route("/<cliente_id>")
@permiso("clientes:ver")
def detalle(cliente_id):
    cliente = repo.get(Cliente, cliente_id)
    if not cliente:
        return redirect(url_for("clientes.lista"))

    boletos = repo.listar(
        Boleto, Boleto.cliente_id == cliente_id, order_by=[cast(Boleto.numero, Integer).desc()]
    )
    recibos = repo.listar(
        Recibo, Recibo.cliente_id == cliente_id, order_by=[cast(Recibo.numero, Integer).desc()]
    )
    return render_template("clientes/detalle.html", cliente=cliente, boletos=boletos, recibos=recibos)


@bp.route("/<cliente_id>/editar", methods=["GET", "POST"])
@permiso("clientes:editar")
def editar(cliente_id):
    cliente = repo.get(Cliente, cliente_id)
    if not cliente:
        return redirect(url_for("clientes.lista"))
    if request.method == "POST":
        repo.actualizar(Cliente, cliente_id, _campos_desde(request.form))
        return redirect(url_for("clientes.detalle", cliente_id=cliente_id))
    return render_template("clientes/form.html", cliente=cliente)


@bp.route("/<cliente_id>/eliminar", methods=["POST"])
@permiso("clientes:eliminar")
def eliminar(cliente_id):
    cliente = repo.get(Cliente, cliente_id)
    if not cliente:
        return redirect(url_for("clientes.lista"))
    boletos = Session.scalar(select(func.count()).select_from(Boleto).where(Boleto.cliente_id == cliente_id))
    recibos = Session.scalar(select(func.count()).select_from(Recibo).where(Recibo.cliente_id == cliente_id))
    if boletos or recibos:
        flash(
            f"No se puede eliminar a «{cliente['nombre']}»: tiene {boletos} boleto(s) y {recibos} recibo(s). "
            "Eliminá primero esos documentos.", "error",
        )
        return redirect(url_for("clientes.detalle", cliente_id=cliente_id))
    Session.execute(delete(Equipo).where(Equipo.cliente_id == cliente_id))
    Session.delete(Session.get(Cliente, cliente_id))
    Session.commit()
    flash("Cliente eliminado.", "success")
    return redirect(url_for("clientes.lista"))
