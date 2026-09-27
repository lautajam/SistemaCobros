from flask import Blueprint, current_app, render_template, request

from .. import csv_utils, models

bp = Blueprint("historial", __name__, url_prefix="/historial")


def _clientes_por_id():
    clientes = csv_utils.read_all(current_app.config["CLIENTES_CSV"], models.CLIENTE_FIELDS)
    return {c["id"]: c for c in clientes}


@bp.route("/")
def index():
    tab = request.args.get("tab", "boletos")
    q = (request.args.get("q") or "").strip().lower()
    fecha = (request.args.get("fecha") or "").strip()
    clientes = _clientes_por_id()

    def nombre_cliente(cliente_id):
        c = clientes.get(cliente_id)
        return c["nombre"] if c else "(cliente no encontrado)"

    if tab == "recibos":
        registros = csv_utils.read_all(current_app.config["RECIBOS_CSV"], models.RECIBO_FIELDS)
        for r in registros:
            r["cliente_nombre"] = nombre_cliente(r["cliente_id"])
        if q:
            registros = [
                r for r in registros
                if q in r["numero"].lower()
                or q in r["cliente_nombre"].lower()
                or q in r["forma_pago"].lower()
                or q in r["importe"].lower()
            ]
        if fecha:
            registros = [r for r in registros if r["fecha"] == fecha]
        registros.sort(key=lambda r: r["numero"], reverse=True)
    else:
        tab = "boletos"
        registros = csv_utils.read_all(current_app.config["BOLETOS_CSV"], models.BOLETO_FIELDS)
        for b in registros:
            b["cliente_nombre"] = nombre_cliente(b["cliente_id"])
        if q:
            registros = [
                b for b in registros
                if q in b["numero"].lower()
                or q in b["cliente_nombre"].lower()
                or q in b["equipo"].lower()
                or q in b["marca"].lower()
                or q in b["modelo"].lower()
                or q in b["numero_serie"].lower()
            ]
        if fecha:
            registros = [b for b in registros if b["fecha"] == fecha]
        registros.sort(key=lambda b: b["numero"], reverse=True)

    return render_template("historial/index.html", tab=tab, registros=registros, q=q, fecha=fecha)
