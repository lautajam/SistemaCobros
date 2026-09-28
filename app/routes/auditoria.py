"""Registro de modificaciones y eliminaciones de clientes, boletos y recibos (solo administrador)."""

from flask import Blueprint, render_template, request
from sqlalchemy import select

from .. import auditoria as logica
from ..auth import permiso, ROL_ADMIN
from ..db import Session
from ..models import Usuario

bp = Blueprint("auditoria", __name__, url_prefix="/auditoria")

DOCUMENTOS_VALIDOS = ("boleto", "recibo", "cliente")


@bp.route("/")
@permiso("auditoria:ver")
def index():
    documento = (request.args.get("documento") or "").strip()
    if documento not in DOCUMENTOS_VALIDOS:
        documento = ""

    usuario_id_txt = (request.args.get("usuario_id") or "").strip()
    usuario_id = int(usuario_id_txt) if usuario_id_txt.isdigit() else None

    registros = logica.recientes(documento=documento or None, usuario_id=usuario_id)
    admins = list(Session.scalars(
        select(Usuario).where(Usuario.rol == ROL_ADMIN).order_by(Usuario.nombre)
    ))
    return render_template(
        "auditoria/index.html", registros=registros, documento=documento,
        usuario_id=usuario_id_txt, admins=admins, documentos=logica.DOCUMENTOS,
    )
