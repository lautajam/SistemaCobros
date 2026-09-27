from flask import Blueprint, flash, redirect, send_file, url_for

from .. import documentos
from ..auth import permiso

bp = Blueprint("blancos", __name__, url_prefix="/blancos")


@bp.route("/boleto")
@permiso("blancos:ver")
def boleto():
    try:
        ruta = documentos.generar_pdf_blanco("boleto")
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("main.index"))
    return send_file(ruta, as_attachment=True)


@bp.route("/recibo")
@permiso("blancos:ver")
def recibo():
    try:
        ruta = documentos.generar_pdf_blanco("recibo")
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("main.index"))
    return send_file(ruta, as_attachment=True)
