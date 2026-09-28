from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import Integer, cast, delete, func, or_, select

from .. import auditoria, counters, models, repo
from ..auth import permiso, tiene_permiso
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


ETIQUETAS_OBLIGATORIAS = {
    "nombre": "el nombre", "dni_cuit": "el DNI / CUIT", "telefono": "el teléfono", "email": "el email",
    "direccion": "la dirección", "localidad": "la localidad", "codigo_postal": "el código postal",
}


def validar_cliente(datos):
    """Todos los datos del cliente son obligatorios, salvo las observaciones (siempre opcionales),
    tanto al crearlo como al modificarlo. Devuelve un mensaje de error o None."""
    faltan = [texto for campo, texto in ETIQUETAS_OBLIGATORIAS.items() if not (datos.get(campo) or "").strip()]
    if faltan:
        return "Falta completar: " + ", ".join(faltan) + "."
    email = datos["email"].strip()
    if "@" not in email or "." not in email.split("@", 1)[1] or " " in email:
        return "El email no es válido."
    return None


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
    # Solo el admin puede pedir ver los deshabilitados; para el técnico la búsqueda
    # siempre excluye a los clientes deshabilitados, sin importar lo que pida la URL.
    estado = (request.args.get("estado") or "activos").strip()
    if estado not in ("activos", "todos") or not tiene_permiso(current_user, "clientes:editar"):
        estado = "activos"
    criterios = [_criterio_busqueda(q, incluir_email=True)] if q else []
    if estado == "activos":
        criterios.append(Cliente.activo.is_(True))
    clientes = repo.listar(Cliente, *criterios, order_by=[func.lower(Cliente.nombre)])
    return render_template("clientes/lista.html", clientes=clientes, q=request.args.get("q", ""), estado=estado)


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso("clientes:crear")
def nuevo():
    if request.method == "POST":
        error = validar_cliente(request.form)
        if error:
            return render_template("clientes/form.html", cliente=None, valores=_campos_desde(request.form), error=error), 400
        cliente = crear_cliente(request.form)
        return redirect(url_for("clientes.detalle", cliente_id=cliente["id"]))
    return render_template("clientes/form.html", cliente=None, valores={})


@bp.route("/api/crear-rapido", methods=["POST"])
@permiso("clientes:crear")
def crear_rapido():
    """Endpoint AJAX: crea un cliente sin recargar la página (usado desde el
    formulario de boleto/recibo)."""
    datos = request.get_json(force=True, silent=True) or {}
    error = validar_cliente(datos)
    if error:
        return jsonify({"error": error}), 400
    cliente = crear_cliente(datos)
    return jsonify(cliente)


@bp.route("/api/buscar")
@permiso("clientes:ver")
def api_buscar():
    # El buscador de boletos/recibos nunca ofrece un cliente deshabilitado: no se le
    # pueden generar documentos nuevos.
    q = (request.args.get("q") or "").strip()
    criterios = [Cliente.activo.is_(True)]
    if q:
        criterios.append(_criterio_busqueda(q, incluir_email=False))
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
        error = validar_cliente(request.form)
        if error:
            return render_template("clientes/form.html", cliente=cliente, valores=_campos_desde(request.form), error=error), 400
        cambios, a_guardar = auditoria.diferencias("cliente", cliente, _campos_desde(request.form))
        if cambios:
            # Se identifica por su nombre (no tiene "número" como un boleto o recibo).
            auditoria.registrar("cliente", {**cliente, "numero": cliente["nombre"]}, "editado", cambios)
        repo.actualizar(Cliente, cliente_id, a_guardar)
        return redirect(url_for("clientes.detalle", cliente_id=cliente_id))
    return render_template("clientes/form.html", cliente=cliente, valores=cliente)


@bp.route("/<cliente_id>/estado", methods=["POST"])
@permiso("clientes:editar")
def estado(cliente_id):
    cliente = repo.get(Cliente, cliente_id)
    if cliente is None:
        abort(404)
    nuevo_valor = not cliente["activo"]
    cambios, a_guardar = auditoria.diferencias("cliente", cliente, {"activo": nuevo_valor})
    auditoria.registrar("cliente", {**cliente, "numero": cliente["nombre"]}, "editado", cambios)  # se confirma junto con el cambio
    repo.actualizar(Cliente, cliente_id, a_guardar)
    if nuevo_valor:
        flash(f"Cliente «{cliente['nombre']}» habilitado: vuelve a aparecer en la búsqueda.", "success")
    else:
        flash(f"Cliente «{cliente['nombre']}» deshabilitado: ya no aparece en la búsqueda ni se le pueden generar documentos nuevos. Su historial no cambia.", "success")
    return redirect(url_for("clientes.detalle", cliente_id=cliente_id))


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
    auditoria.registrar(
        "cliente", {**cliente, "numero": cliente["nombre"]}, "eliminado", auditoria.instantanea("cliente", cliente)
    )
    Session.execute(delete(Equipo).where(Equipo.cliente_id == cliente_id))
    Session.delete(Session.get(Cliente, cliente_id))
    Session.commit()
    flash("Cliente eliminado.", "success")
    return redirect(url_for("clientes.lista"))
