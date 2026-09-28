from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from .. import auditoria, counters, documentos, fechas, formularios, models, repo
from ..auth import permiso
from ..db import Session
from ..models import Boleto, Cliente, Recibo, Usuario

bp = Blueprint("recibos", __name__, url_prefix="/recibos")

CAMPOS_EDITABLES = ["fecha", "equipo", "trabajo", "descripcion", "importe", "forma_pago", "observaciones"]


def _get_cliente(cliente_id):
    return repo.get(Cliente, cliente_id)


def _get_boleto(boleto_id):
    if not boleto_id:
        return None
    return repo.get(Boleto, boleto_id)


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso("recibos:crear")
def nuevo():
    boleto_id = request.values.get("boleto_id", "").strip()
    boleto = _get_boleto(boleto_id)

    if request.method == "POST":
        cliente_id = (request.form.get("cliente_id") or "").strip()
        cliente = _get_cliente(cliente_id)
        if not cliente or not cliente.get("activo", True):
            error = "Debe seleccionar (o crear) un cliente antes de guardar." if not cliente else                 "Este cliente está deshabilitado: no se le pueden generar documentos nuevos. Podés habilitarlo desde su ficha."
            return render_template(
                "recibos/form.html", recibo=None, boleto=boleto, fecha_hoy=date.today().isoformat(), error=error,
            ), 400

        error, equipo = formularios.validar_fecha_y_equipo(request.form)
        if error:
            return render_template(
                "recibos/form.html", recibo=None, boleto=boleto, fecha_hoy=date.today().isoformat(), error=error,
            ), 400

        numero = models.format_recibo_numero(counters.next_number("recibo"))
        recibo = repo.insertar(Recibo, {
            "id": models.format_recibo_id(numero),
            "numero": numero,
            "cliente_id": cliente_id,
            "creado_por_id": current_user.id,
            "boleto_id": boleto["id"] if boleto else "",
            "fecha": (fechas.parsear(request.form.get("fecha")) or date.today()).isoformat(),
            "equipo": equipo,
            "trabajo": request.form.get("trabajo", ""),
            "descripcion": request.form.get("descripcion", ""),
            "importe": request.form.get("importe", ""),
            "forma_pago": request.form.get("forma_pago", ""),
            "observaciones": request.form.get("observaciones", ""),
        })
        try:
            documentos.generar_pdf_recibo(recibo, cliente)
        except RuntimeError as e:
            flash(f"El recibo N.º {recibo['numero']} se guardó correctamente, pero no se pudo generar el PDF: {e}", "warning")
        return redirect(url_for("recibos.detalle", recibo_id=recibo["id"]))

    cliente_prefill = _get_cliente(boleto["cliente_id"]) if boleto else None
    return render_template(
        "recibos/form.html", recibo=None, boleto=boleto, cliente_prefill=cliente_prefill,
        fecha_hoy=date.today().isoformat(),
    )


@bp.route("/<recibo_id>")
@permiso("recibos:ver")
def detalle(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if not recibo:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(recibo["cliente_id"])
    boleto = _get_boleto(recibo.get("boleto_id"))
    creador = Session.get(Usuario, recibo["creado_por_id"]) if recibo.get("creado_por_id") else None
    return render_template(
        "recibos/detalle.html", recibo=recibo, cliente=cliente, boleto=boleto, creador=creador,
        historial=auditoria.historial("recibo", recibo_id),
    )


@bp.route("/<recibo_id>/editar", methods=["GET", "POST"])
@permiso("recibos:editar")  # solo administrador: un recibo emitido no lo toca nadie más
def editar(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if not recibo:
        return redirect(url_for("historial.index"))
    boleto = _get_boleto(recibo.get("boleto_id"))
    cliente = _get_cliente(recibo["cliente_id"])

    if request.method == "POST":
        error, equipo = formularios.validar_fecha_y_equipo(request.form, recibo.get("equipo", ""))
        if error:
            return render_template("recibos/form.html", recibo=recibo, boleto=boleto, cliente_prefill=cliente, error=error), 400
        enviados = {campo: request.form.get(campo, "") for campo in CAMPOS_EDITABLES}
        enviados["equipo"] = equipo
        if not fechas.parsear(enviados["fecha"]):
            del enviados["fecha"]  # vacía: se conserva la fecha original
        cambios, a_guardar = auditoria.diferencias("recibo", recibo, enviados)
        if not cambios:
            flash("No cambiaste ningún dato: el recibo quedó igual.", "info")
            return redirect(url_for("recibos.detalle", recibo_id=recibo_id))
        auditoria.registrar("recibo", recibo, "editado", cambios)  # se confirma junto con el cambio
        repo.actualizar(Recibo, recibo_id, a_guardar)
        recibo = repo.get(Recibo, recibo_id)
        try:
            documentos.regenerar_pdf("recibo", recibo, cliente)
        except RuntimeError as e:
            flash(f"El cambio se guardó, pero no se pudo actualizar el PDF: {e}", "warning")
        else:
            flash("Recibo editado. El cambio quedó registrado a tu nombre.", "success")
        return redirect(url_for("recibos.detalle", recibo_id=recibo_id))

    return render_template("recibos/form.html", recibo=recibo, boleto=boleto, cliente_prefill=cliente)


@bp.route("/<recibo_id>/pdf")
@permiso("recibos:ver")
def pdf(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if not recibo:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(recibo["cliente_id"])
    try:
        ruta = documentos.pdf_emitido("recibo", recibo, cliente)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("recibos.detalle", recibo_id=recibo_id))
    return send_file(ruta, as_attachment=False)


@bp.route("/<recibo_id>/eliminar", methods=["POST"])
@permiso("recibos:eliminar")
def eliminar(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if recibo:
        cliente = _get_cliente(recibo["cliente_id"]) or {}
        auditoria.registrar("recibo", recibo, "eliminado", auditoria.instantanea("recibo", recibo, cliente.get("nombre", "")))
        repo.eliminar(Recibo, recibo_id)
    return redirect(url_for("historial.index"))
