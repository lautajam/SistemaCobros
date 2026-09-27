from flask import Blueprint, flash, redirect, send_file, url_for

from .. import documentos

bp = Blueprint("blancos", __name__, url_prefix="/blancos")


@bp.route("/boleto")
def boleto():
    try:
        ruta = documentos.generar_pdf_blanco("boleto")
    except RuntimeError as e:
        flash(str(e))
        return redirect(url_for("main.index"))
    return send_file(ruta, as_attachment=True)


@bp.route("/recibo")
def recibo():
    try:
        ruta = documentos.generar_pdf_blanco("recibo")
    except RuntimeError as e:
        flash(str(e))
        return redirect(url_for("main.index"))
    return send_file(ruta, as_attachment=True)
