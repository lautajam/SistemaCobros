"""Validaciones compartidas por los formularios de boletos y recibos."""

from . import fechas, tipos


def validar_fecha_y_equipo(formulario, equipo_actual=""):
    """Devuelve (error, equipo_oficial). La fecha vacía es válida (se usa hoy / la que ya tenía);
    el tipo de equipo tiene que salir de la lista que administra el admin."""
    texto = (formulario.get("fecha") or "").strip()
    if texto and fechas.parsear(texto) is None:
        return "La fecha no es válida. Usá el formato dd/mm/aaaa.", ""
    equipo, error = tipos.validar_equipo(formulario.get("equipo"), equipo_actual)
    return error, equipo
