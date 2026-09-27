from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from .. import counters, documentos, models, repo
from ..models import Boleto, Cliente, Recibo

bp = Blueprint("recibos", __name__, url_prefix="/recibos")

CAMPOS_EDITABLES = ["fecha", "trabajo", "descripcion", "importe", "forma_pago", "observaciones"]


def _get_cliente(cliente_id):
    return repo.get(Cliente, cliente_id)


def _get_boleto(boleto_id):
    if not boleto_id:
        return None
    return repo.get(Boleto, boleto_id)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    boleto_id = request.values.get("boleto_id", "").strip()
    boleto = _get_boleto(boleto_id)

    if request.method == "POST":
        cliente_id = (request.form.get("cliente_id") or "").strip()
        cliente = _get_cliente(cliente_id)
        if not cliente:
            return render_template(
                "recibos/form.html", recibo=None, boleto=boleto,
                error="Debe seleccionar (o crear) un cliente antes de guardar.",
            ), 400

        numero = models.format_recibo_numero(counters.next_number("recibo"))
        recibo = repo.insertar(Recibo, {
            "id": models.format_recibo_id(numero),
            "numero": numero,
            "cliente_id": cliente_id,
            "boleto_id": boleto["id"] if boleto else "",
            "fecha": request.form.get("fecha") or date.today().isoformat(),
            "trabajo": request.form.get("trabajo", ""),
            "descripcion": request.form.get("descripcion", ""),
            "importe": request.form.get("importe", ""),
            "forma_pago": request.form.get("forma_pago", ""),
            "observaciones": request.form.get("observaciones", ""),
        })
        try:
            documentos.generar_pdf_recibo(recibo, cliente)
        except RuntimeError as e:
            flash(f"El recibo N.º {recibo['numero']} se guardó correctamente, pero no se pudo generar el PDF: {e}")
        return redirect(url_for("recibos.detalle", recibo_id=recibo["id"]))

    cliente_prefill = _get_cliente(boleto["cliente_id"]) if boleto else None
    return render_template("recibos/form.html", recibo=None, boleto=boleto, cliente_prefill=cliente_prefill)


@bp.route("/<recibo_id>")
def detalle(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if not recibo:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(recibo["cliente_id"])
    boleto = _get_boleto(recibo.get("boleto_id"))
    return render_template("recibos/detalle.html", recibo=recibo, cliente=cliente, boleto=boleto)


@bp.route("/<recibo_id>/editar", methods=["GET", "POST"])
def editar(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if not recibo:
        return redirect(url_for("historial.index"))

    if request.method == "POST":
        cambios = {campo: request.form.get(campo, "") for campo in CAMPOS_EDITABLES}
        repo.actualizar(Recibo, recibo_id, cambios)
        return redirect(url_for("recibos.detalle", recibo_id=recibo_id))

    boleto = _get_boleto(recibo.get("boleto_id"))
    cliente_prefill = _get_cliente(recibo["cliente_id"])
    return render_template("recibos/form.html", recibo=recibo, boleto=boleto, cliente_prefill=cliente_prefill)


@bp.route("/<recibo_id>/pdf")
def pdf(recibo_id):
    recibo = repo.get(Recibo, recibo_id)
    if not recibo:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(recibo["cliente_id"])
    try:
        ruta = documentos.generar_pdf_recibo(recibo, cliente)
    except RuntimeError as e:
        flash(str(e))
        return redirect(url_for("recibos.detalle", recibo_id=recibo_id))
    return send_file(ruta, as_attachment=False)


@bp.route("/<recibo_id>/eliminar", methods=["POST"])
def eliminar(recibo_id):
    repo.eliminar(Recibo, recibo_id)
    return redirect(url_for("historial.index"))
