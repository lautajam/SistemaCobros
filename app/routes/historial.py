from datetime import date

from flask import Blueprint, render_template, request
from sqlalchemy import Integer, String, cast, or_, select

from ..db import Session
from ..models import Boleto, Cliente, Recibo

bp = Blueprint("historial", __name__, url_prefix="/historial")


def _con_cliente(modelo, criterio_texto, q, fecha):
    """Lista `modelo` junto al nombre del cliente, con búsqueda de texto y
    filtro por fecha resueltos en la base."""
    consulta = select(modelo, Cliente.nombre).join(Cliente, modelo.cliente_id == Cliente.id)
    if q:
        consulta = consulta.where(or_(*[c.icontains(q, autoescape=True) for c in criterio_texto(modelo)]))
    if fecha:
        try:
            consulta = consulta.where(modelo.fecha == date.fromisoformat(fecha))
        except ValueError:
            pass
    consulta = consulta.order_by(cast(modelo.numero, Integer).desc())

    registros = []
    for objeto, nombre_cliente in Session.execute(consulta):
        registro = objeto.to_dict()
        registro["cliente_nombre"] = nombre_cliente
        registros.append(registro)
    return registros


def _campos_boleto(modelo):
    return [
        modelo.numero, Cliente.nombre, modelo.equipo, modelo.marca,
        modelo.modelo, modelo.numero_serie,
    ]


def _campos_recibo(modelo):
    return [modelo.numero, Cliente.nombre, modelo.forma_pago, cast(modelo.importe, String)]


@bp.route("/")
def index():
    tab = request.args.get("tab", "boletos")
    q = (request.args.get("q") or "").strip()
    fecha = (request.args.get("fecha") or "").strip()

    if tab == "recibos":
        registros = _con_cliente(Recibo, _campos_recibo, q, fecha)
    else:
        tab = "boletos"
        registros = _con_cliente(Boleto, _campos_boleto, q, fecha)

    return render_template("historial/index.html", tab=tab, registros=registros, q=q, fecha=fecha)
