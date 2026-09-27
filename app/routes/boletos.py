import uuid
from datetime import date

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for

from .. import counters, csv_utils, documentos, models

bp = Blueprint("boletos", __name__, url_prefix="/boletos")

CAMPOS_EDITABLES = [
    "fecha", "hora", "equipo", "marca", "modelo", "numero_serie",
    "especificaciones", "accesorios", "estado_fisico", "problema", "observaciones",
]


def _get_cliente(cliente_id):
    return csv_utils.get_row(current_app.config["CLIENTES_CSV"], models.CLIENTE_FIELDS, "id", cliente_id)


def _upsert_equipo(cliente_id, boleto):
    """Mantiene una entidad liviana de 'equipos' para poder consultar en el
    futuro el historial de reparaciones de un mismo equipo (requisito 21).
    No es obligatorio para el usuario: se completa solo si cargó N.º de serie.
    """
    numero_serie = (boleto.get("numero_serie") or "").strip()
    if not numero_serie:
        return
    path = current_app.config["EQUIPOS_CSV"]
    equipos = csv_utils.read_all(path, models.EQUIPO_FIELDS)
    for equipo in equipos:
        if equipo["cliente_id"] == cliente_id and equipo["numero_serie"] == numero_serie:
            equipo["tipo"] = boleto.get("equipo", equipo["tipo"])
            equipo["marca"] = boleto.get("marca", equipo["marca"])
            equipo["modelo"] = boleto.get("modelo", equipo["modelo"])
            csv_utils.write_all(path, models.EQUIPO_FIELDS, equipos)
            return
    nuevo_equipo = {
        "id": f"E{uuid.uuid4().hex[:8]}",
        "cliente_id": cliente_id,
        "tipo": boleto.get("equipo", ""),
        "marca": boleto.get("marca", ""),
        "modelo": boleto.get("modelo", ""),
        "numero_serie": numero_serie,
    }
    csv_utils.append_row(path, models.EQUIPO_FIELDS, nuevo_equipo)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    base_dir = current_app.config["BASE_DIR"]

    if request.method == "POST":
        cliente_id = (request.form.get("cliente_id") or "").strip()
        cliente = _get_cliente(cliente_id)
        if not cliente:
            return render_template(
                "boletos/form.html", boleto=None,
                error="Debe seleccionar (o crear) un cliente antes de guardar.",
            ), 400

        numero = models.format_boleto_numero(counters.next_number(base_dir, "boleto"))
        boleto = {
            "id": models.format_boleto_id(numero),
            "numero": numero,
            "cliente_id": cliente_id,
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
        }
        csv_utils.append_row(current_app.config["BOLETOS_CSV"], models.BOLETO_FIELDS, boleto)
        _upsert_equipo(cliente_id, boleto)
        try:
            documentos.generar_pdf_boleto(base_dir, boleto, cliente)
        except RuntimeError as e:
            flash(f"El boleto N.º {boleto['numero']} se guardó correctamente, pero no se pudo generar el PDF: {e}")
        return redirect(url_for("boletos.detalle", boleto_id=boleto["id"]))

    cliente_id_prefill = request.args.get("cliente_id", "")
    cliente_prefill = _get_cliente(cliente_id_prefill) if cliente_id_prefill else None
    return render_template(
        "boletos/form.html", boleto=None,
        cliente_id_prefill=cliente_id_prefill, cliente_prefill=cliente_prefill,
    )


@bp.route("/<boleto_id>")
def detalle(boleto_id):
    boleto = csv_utils.get_row(current_app.config["BOLETOS_CSV"], models.BOLETO_FIELDS, "id", boleto_id)
    if not boleto:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(boleto["cliente_id"])
    recibos = [
        r for r in csv_utils.read_all(current_app.config["RECIBOS_CSV"], models.RECIBO_FIELDS)
        if r["boleto_id"] == boleto_id
    ]
    return render_template("boletos/detalle.html", boleto=boleto, cliente=cliente, recibos=recibos)


@bp.route("/<boleto_id>/editar", methods=["GET", "POST"])
def editar(boleto_id):
    path = current_app.config["BOLETOS_CSV"]
    boleto = csv_utils.get_row(path, models.BOLETO_FIELDS, "id", boleto_id)
    if not boleto:
        return redirect(url_for("historial.index"))

    if request.method == "POST":
        cambios = {campo: request.form.get(campo, "") for campo in CAMPOS_EDITABLES}
        csv_utils.update_row(path, models.BOLETO_FIELDS, "id", boleto_id, cambios)
        return redirect(url_for("boletos.detalle", boleto_id=boleto_id))

    cliente = _get_cliente(boleto["cliente_id"])
    return render_template("boletos/form.html", boleto=boleto, cliente_prefill=cliente)


@bp.route("/<boleto_id>/pdf")
def pdf(boleto_id):
    boleto = csv_utils.get_row(current_app.config["BOLETOS_CSV"], models.BOLETO_FIELDS, "id", boleto_id)
    if not boleto:
        return redirect(url_for("historial.index"))
    cliente = _get_cliente(boleto["cliente_id"])
    try:
        ruta = documentos.generar_pdf_boleto(current_app.config["BASE_DIR"], boleto, cliente)
    except RuntimeError as e:
        flash(str(e))
        return redirect(url_for("boletos.detalle", boleto_id=boleto_id))
    return send_file(ruta, as_attachment=False)


@bp.route("/<boleto_id>/eliminar", methods=["POST"])
def eliminar(boleto_id):
    csv_utils.delete_row(current_app.config["BOLETOS_CSV"], models.BOLETO_FIELDS, "id", boleto_id)
    return redirect(url_for("historial.index"))


@bp.route("/<boleto_id>/crear-recibo")
def crear_recibo(boleto_id):
    return redirect(url_for("recibos.nuevo", boleto_id=boleto_id))
