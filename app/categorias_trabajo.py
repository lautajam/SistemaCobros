"""
categorias_trabajo.py
----------------------
Lista de categorías del tarifario (Reparación, Mantenimiento, Instalación...). La
administra el admin (pantalla «Tarifario → Categorías») y es la fuente de la que se
elige la categoría de cada trabajo: no se puede escribir una categoría libre.
"""

from sqlalchemy import func, select

from .db import Session
from .models import CategoriaTrabajo


def normalizar(nombre):
    """Recorta y colapsa espacios repetidos."""
    return " ".join((nombre or "").split())


def nombres():
    return list(Session.scalars(select(CategoriaTrabajo.nombre).order_by(func.lower(CategoriaTrabajo.nombre))))


def validar_categoria(valor, actual=""):
    """Comprueba la categoría enviada por el formulario de un trabajo. Devuelve
    (nombre_oficial, error). Al editar se acepta el valor que ya tenía el trabajo
    (`actual`) aunque la categoría se haya eliminado de la lista."""
    valor = normalizar(valor)
    if not valor:
        return "", "Elegí una categoría de la lista."
    if actual and valor.lower() == normalizar(actual).lower():
        return normalizar(actual), None
    for oficial in nombres():
        if oficial.lower() == valor.lower():
            return oficial, None
    return "", "Elegí una categoría de la lista."
