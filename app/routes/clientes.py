from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from .. import counters, csv_utils, models

bp = Blueprint("clientes", __name__, url_prefix="/clientes")


def _path():
    return current_app.config["CLIENTES_CSV"]


def _todos():
    return csv_utils.read_all(_path(), models.CLIENTE_FIELDS)


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


def crear_cliente(formulario) -> dict:
    """Crea un cliente nuevo con ID interno único y permanente (nunca el
    nombre). Usado tanto por el formulario propio de clientes como por el
    botón 'Nuevo cliente' dentro de boletos/recibos."""
    base_dir = current_app.config["BASE_DIR"]
    numero = counters.next_number(base_dir, "cliente")
    cliente = {"id": models.format_cliente_id(numero), **_campos_desde(formulario)}
    csv_utils.append_row(_path(), models.CLIENTE_FIELDS, cliente)
    return cliente


@bp.route("/")
def lista():
    q = (request.args.get("q") or "").strip().lower()
    clientes = _todos()
    if q:
        clientes = [
            c for c in clientes
            if q in c["nombre"].lower()
            or q in c["dni_cuit"].lower()
            or q in c["telefono"].lower()
            or q in c["email"].lower()
        ]
    clientes.sort(key=lambda c: c["nombre"].lower())
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
    q = (request.args.get("q") or "").strip().lower()
    clientes = _todos()
    if q:
        clientes = [
            c for c in clientes
            if q in c["nombre"].lower()
            or q in c["dni_cuit"].lower()
            or q in c["telefono"].lower()
        ]
    clientes.sort(key=lambda c: c["nombre"].lower())
    return jsonify(clientes[:25])


@bp.route("/<cliente_id>")
def detalle(cliente_id):
    cliente = csv_utils.get_row(_path(), models.CLIENTE_FIELDS, "id", cliente_id)
    if not cliente:
        return redirect(url_for("clientes.lista"))

    boletos = [
        b for b in csv_utils.read_all(current_app.config["BOLETOS_CSV"], models.BOLETO_FIELDS)
        if b["cliente_id"] == cliente_id
    ]
    recibos = [
        r for r in csv_utils.read_all(current_app.config["RECIBOS_CSV"], models.RECIBO_FIELDS)
        if r["cliente_id"] == cliente_id
    ]
    boletos.sort(key=lambda b: b["numero"], reverse=True)
    recibos.sort(key=lambda r: r["numero"], reverse=True)
    return render_template("clientes/detalle.html", cliente=cliente, boletos=boletos, recibos=recibos)


@bp.route("/<cliente_id>/editar", methods=["GET", "POST"])
def editar(cliente_id):
    cliente = csv_utils.get_row(_path(), models.CLIENTE_FIELDS, "id", cliente_id)
    if not cliente:
        return redirect(url_for("clientes.lista"))
    if request.method == "POST":
        csv_utils.update_row(_path(), models.CLIENTE_FIELDS, "id", cliente_id, _campos_desde(request.form))
        return redirect(url_for("clientes.detalle", cliente_id=cliente_id))
    return render_template("clientes/form.html", cliente=cliente)
