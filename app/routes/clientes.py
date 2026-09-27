from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import Integer, cast, func, or_

from .. import counters, models, repo
from ..models import Boleto, Cliente, Recibo

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
def lista():
    q = (request.args.get("q") or "").strip()
    criterios = [_criterio_busqueda(q, incluir_email=True)] if q else []
    clientes = repo.listar(Cliente, *criterios, order_by=[func.lower(Cliente.nombre)])
    return render_template("clientes/lista.html", clientes=clientes, q=request.args.get("q", ""))


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        cliente = crear_cliente(request.form)
        return redirect(url_for("clientes.detalle", cliente_id=cliente["id"]))
    return render_template("clientes/form.html", cliente=None)


@bp.route("/api/crear-rapido", methods=["POST"])
def crear_rapido():
    """Endpoint AJAX: crea un cliente sin recargar la página (usado desde el
    formulario de boleto/recibo)."""
    datos = request.get_json(force=True, silent=True) or {}
    if not (datos.get("nombre") or "").strip():
        return jsonify({"error": "El nombre es obligatorio."}), 400
    cliente = crear_cliente(datos)
    return jsonify(cliente)


@bp.route("/api/buscar")
def api_buscar():
    q = (request.args.get("q") or "").strip()
    criterios = [_criterio_busqueda(q, incluir_email=False)] if q else []
    clientes = repo.listar(Cliente, *criterios, order_by=[func.lower(Cliente.nombre)])
    return jsonify(clientes[:25])


@bp.route("/<cliente_id>")
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
def editar(cliente_id):
    cliente = repo.get(Cliente, cliente_id)
    if not cliente:
        return redirect(url_for("clientes.lista"))
    if request.method == "POST":
        repo.actualizar(Cliente, cliente_id, _campos_desde(request.form))
        return redirect(url_for("clientes.detalle", cliente_id=cliente_id))
    return render_template("clientes/form.html", cliente=cliente)
