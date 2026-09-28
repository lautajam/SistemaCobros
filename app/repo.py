"""
repo.py
-------
Capa de acceso a datos sobre PostgreSQL. Expone una API chica que devuelve
dicts de strings (igual que antes con los CSV), así las rutas y plantillas
no dependen de SQLAlchemy.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import Date, Numeric, select

from . import fechas
from .db import Session


def _parse_fecha(valor):
    return fechas.parsear(valor)


def _parse_importe(valor):
    if isinstance(valor, Decimal):
        return valor
    texto = (str(valor) if valor is not None else "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _coerce(modelo, datos, para_actualizar=False):
    """Convierte los strings del formulario a los tipos de la tabla."""
    columnas = modelo.__table__.columns
    resultado = {}
    for clave, valor in datos.items():
        columna = columnas.get(clave)
        if columna is None:
            continue
        if isinstance(columna.type, Date):
            valor = _parse_fecha(valor)
            if valor is None and not columna.nullable:
                if para_actualizar:
                    continue
                valor = date.today()
        elif isinstance(columna.type, Numeric):
            valor = _parse_importe(valor)
        elif columna.foreign_keys and valor == "":
            valor = None
        resultado[clave] = valor
    return resultado


def get(modelo, id_):
    objeto = Session.get(modelo, id_)
    return objeto.to_dict() if objeto else None


def listar(modelo, *criterios, order_by=()):
    consulta = select(modelo)
    if criterios:
        consulta = consulta.where(*criterios)
    if order_by:
        consulta = consulta.order_by(*order_by)
    return [objeto.to_dict() for objeto in Session.scalars(consulta)]


def insertar(modelo, datos):
    objeto = modelo(**_coerce(modelo, datos))
    Session.add(objeto)
    try:
        Session.commit()
    except Exception:
        Session.rollback()
        raise
    return objeto.to_dict()


def actualizar(modelo, id_, cambios):
    objeto = Session.get(modelo, id_)
    if objeto is None:
        return False
    for clave, valor in _coerce(modelo, cambios, para_actualizar=True).items():
        setattr(objeto, clave, valor)
    try:
        Session.commit()
    except Exception:
        Session.rollback()
        raise
    return True


def eliminar(modelo, id_):
    objeto = Session.get(modelo, id_)
    if objeto is None:
        return False
    Session.delete(objeto)
    try:
        Session.commit()
    except Exception:
        Session.rollback()
        raise
    return True
