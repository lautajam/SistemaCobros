"""Registro de modificaciones y eliminaciones de boletos y recibos (solo administrador)."""

from flask import Blueprint, render_template

from .. import auditoria as logica
from ..auth import permiso

bp = Blueprint("auditoria", __name__, url_prefix="/auditoria")


@bp.route("/")
@permiso("auditoria:ver")
def index():
    return render_template("auditoria/index.html", registros=logica.recientes())
