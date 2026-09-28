"""
tipos.py
--------
Lista de tipos de equipo (PC, Notebook, Impresora...). La administra el admin
(pantalla "Tipos de equipo") y es la única fuente de la que se elige el tipo en
boletos y recibos: no se puede escribir un tipo libre.
"""

from sqlalchemy import func, select

from .db import Session
from .models import TipoEquipo


def normalizar(nombre):
    """Recorta y colapsa espacios repetidos."""
    return " ".join((nombre or "").split())


def nombres():
    """Tipos habilitados: los que se ofrecen al crear un boleto o recibo."""
    return list(Session.scalars(
        select(TipoEquipo.nombre).where(TipoEquipo.activo.is_(True)).order_by(func.lower(TipoEquipo.nombre))
    ))


def validar_equipo(valor, actual=""):
    """Comprueba el tipo enviado por un formulario. Devuelve (nombre_oficial, error).
    Vacío es válido (sin especificar). Al editar se acepta el valor que ya tenía el
    documento (`actual`) aunque el tipo se haya deshabilitado o borrado."""
    valor = normalizar(valor)
    if not valor:
        return "", None
    if actual and valor.lower() == normalizar(actual).lower():
        return normalizar(actual), None
    for oficial in nombres():
        if oficial.lower() == valor.lower():
            return oficial, None
    return "", "Elegí un tipo de equipo de la lista."
