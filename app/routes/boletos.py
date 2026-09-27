import uuid
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from .. import counters, documentos, models, repo
from ..auth import permiso
from ..db import Session
from ..models import Boleto, Cliente, Equipo, Recibo, Usuario

bp = Blueprint("boletos", __name__, url_prefix="/boletos")

CAMPOS_EDITABLES = [
    "fecha", "hora", "equipo", "marca", "modelo", "numero_serie",
    "especificaciones", "accesorios", "estado_fisico", "problema", "observaciones",
]


def _get_cliente(cliente_id):
    return repo.get(Cliente, cliente_id)


def _upsert_equipo(cliente_id, boleto):
    """Mantiene una entidad liviana de 'equipos' para poder consultar en el
    futuro el historial de reparaciones de un mismo equipo. No es obligatorio
    para el usuario: se completa solo si cargó N.º de serie.
    """
    numero_serie = (boleto.get("numero_serie") or "").strip()
    if not numero_serie:
        return
    existente = Session.query(Equipo).filter_by(cliente_id=cliente_id, numero_serie=numero_serie).first()
    if existente:
        repo.actualizar(Equipo, existente.id, {
            "tipo": boleto.get("equipo", existente.tipo),
            "marca": boleto.get("marca", existente.marca),
            "modelo": boleto.get("modelo", existente.modelo),
        })
        return
    repo.insertar(Equipo, {
        "id": f"E{uuid.uuid4().hex[:8]}",
        "cliente_id": cliente_id,
        "tipo": boleto.get("equipo", ""),
        "marca": boleto.get("marca", ""),
        "modelo": boleto.get("modelo", ""),
        "numero_serie": numero_serie,
    })


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso("boletos:crear")
def nuevo():
    if request.method == "POST":
        cliente_id = (request.form.get("cliente_id") or "").strip()
        cliente = _get_cliente(cliente_id)
        if not cliente:
            return render_template(
                "boletos/form.html", boleto=None, fecha_hoy=date.today().isoformat(),
                error="Debe seleccionar (o crear) un cliente antes de guardar.",
            ), 400

        numero = models.format_boleto_numero(counters.next_number("boleto"))
        boleto = repo.insertar(Boleto, {
            "id": models.format_boleto_id(numero),
            "numero": numero,
            "cliente_id": cliente_id,
            "creado_por_id": current_user.id,
            "fecha": request.form.get("fecha") or date.today().isoformat(),
            "hora": request.form.get("hora", ""),
            "equipo": request.form.get("equipo", ""),
            "marca": request.form.get("marca", ""),
            "modelo": request.form.get("modelo", ""),
            "numero_serie": request.form.get("numero_serie", ""),
            "especificaciones": request.form.get("especificaciones", ""),
            "accesorios": request.form.get("accesorios", ""),
            "estado_fisico": request.form.get("estado_fisico", ""),
            "problema": request.form.get("problema", ""),
            "observaciones": request.form.get("observaciones", ""),
        })
        _upsert_equipo(cliente_id, boleto)
        try:
            documentos.generar_pdf_boleto(boleto, cliente)
        except RuntimeError as e:
            flash(f"El boleto N.º {boleto['numero']} se guardó correctamente, pero no se pudo generar el PDF: {e}", "warning")
        return redirect(url_for("boletos.detalle", boleto_id=boleto["id"]))

    cliente_id_prefill = request.args.get("cliente_id", "")
    cliente_prefill = _get_cliente(cliente_id_prefill) if cliente_id_prefill else None
    return render_template(
        "boletos/form.html", boleto=None, fecha_hoy=date.today().isoformat(),
        cliente_id_prefill=cliente_id_prefill, cliente_prefill=cliente_prefill,
    )


@bp.route("/<boleto_id>")
@permiso("boletos:ver")
def detalle(boleto_id):
    boleto = repo.get(Boleto, boleto_id)
    if not boleto:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(boleto["cliente_id"])
    recibos = repo.listar(Recibo, Recibo.boleto_id == boleto_id)
    creador = Session.get(Usuario, boleto["creado_por_id"]) if boleto.get("creado_por_id") else None
    return render_template("boletos/detalle.html", boleto=boleto, cliente=cliente, recibos=recibos, creador=creador)


@bp.route("/<boleto_id>/editar", methods=["GET", "POST"])
@permiso("boletos:editar")
def editar(boleto_id):
    boleto = repo.get(Boleto, boleto_id)
    if not boleto:
        return redirect(url_for("historial.index"))

    if request.method == "POST":
        cambios = {campo: request.form.get(campo, "") for campo in CAMPOS_EDITABLES}
        repo.actualizar(Boleto, boleto_id, cambios)
        return redirect(url_for("boletos.detalle", boleto_id=boleto_id))

    cliente = _get_cliente(boleto["cliente_id"])
    return render_template("boletos/form.html", boleto=boleto, cliente_prefill=cliente)


@bp.route("/<boleto_id>/pdf")
@permiso("boletos:ver")
def pdf(boleto_id):
    boleto = repo.get(Boleto, boleto_id)
    if not boleto:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(boleto["cliente_id"])
    try:
        ruta = documentos.generar_pdf_boleto(boleto, cliente)
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("boletos.detalle", boleto_id=boleto_id))
    return send_file(ruta, as_attachment=False)


@bp.route("/<boleto_id>/eliminar", methods=["POST"])
@permiso("boletos:eliminar")
def eliminar(boleto_id):
    repo.eliminar(Boleto, boleto_id)
    return redirect(url_for("historial.index"))


@bp.route("/<boleto_id>/crear-recibo")
@permiso("recibos:crear")
def crear_recibo(boleto_id):
    return redirect(url_for("recibos.nuevo", boleto_id=boleto_id))
