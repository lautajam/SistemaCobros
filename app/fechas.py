"""
fechas.py
---------
Las fechas se muestran y se escriben como dd/mm/aaaa (formato argentino). Se
guardan en la base como fecha real. Este módulo entiende ambos formatos, para
que el resto del código no tenga que preocuparse por eso.
"""

import re
from datetime import date, datetime

_LATINA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def parsear(valor):
    """Devuelve un `date` a partir de 'dd/mm/aaaa', 'aaaa-mm-dd' o un date; None si está
    vacío o no es una fecha real (por ejemplo 31/02/2026)."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = (str(valor) if valor is not None else "").strip()
    if not texto:
        return None
    partes = None
    coincidencia = _LATINA.match(texto)
    if coincidencia:
        dia, mes, anio = (int(x) for x in coincidencia.groups())
        partes = (anio, mes, dia)
    else:
        coincidencia = _ISO.match(texto)
        if coincidencia:
            partes = tuple(int(x) for x in coincidencia.groups())
    if partes is None:
        return None
    try:
        return date(*partes)
    except ValueError:
        return None


def a_texto(valor):
    """'2026-09-27' (o un date) -> '27/09/2026'. Si no es una fecha, devuelve el texto tal cual."""
    fecha = parsear(valor)
    if fecha is None:
        return str(valor) if valor else ""
    return fecha.strftime("%d/%m/%Y")


def hoy_texto():
    return date.today().strftime("%d/%m/%Y")
