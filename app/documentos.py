"""
documentos.py
-------------
Une los datos (cliente/boleto/recibo/configuración del service) con las
plantillas HTML editables de `templates/` y genera el PDF final en la
carpeta que corresponde, con el nombre de archivo obligatorio.
"""

import os
from datetime import datetime

from flask import current_app

from . import pdf_utils, models


def _fecha_ddmmyyyy(fecha_iso: str) -> str:
    """Convierte una fecha 'YYYY-MM-DD' (la que produce <input type=date>)
    al formato DD-MM-YYYY exigido para los nombres de archivo."""
    if fecha_iso:
        try:
            return datetime.strptime(fecha_iso, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            pass
    return datetime.now().strftime("%d-%m-%Y")


def _service_context(base_dir: str) -> dict:
    # Import diferido para evitar import circular con el blueprint.
    from .routes.configuracion import get_config, _logo_dir

    cfg = get_config(base_dir, current_app.config["CONFIG_CSV"])
    logo_path = ""
    if cfg.get("logo"):
        ruta = os.path.join(_logo_dir(base_dir), cfg["logo"])
        if os.path.exists(ruta):
            logo_path = "file://" + os.path.abspath(ruta)
    return {**cfg, "logo_path": logo_path}


def generar_pdf_boleto(base_dir: str, boleto: dict, cliente: dict) -> str:
    contexto = {
        "service": _service_context(base_dir),
        "cliente": cliente,
        "boleto": boleto,
        "blanco": False,
    }
    html = pdf_utils.render_html_template(
        current_app.config["DOC_TEMPLATES_DIR"], "boleto.html", contexto
    )
    fecha = _fecha_ddmmyyyy(boleto.get("fecha"))
    nombre_archivo = pdf_utils.nombre_pdf_boleto(fecha, cliente.get("nombre", ""), boleto.get("numero", ""))
    destino = os.path.join(current_app.config["DOCUMENTOS_DIR"], "boletos", nombre_archivo)
    pdf_utils.html_to_pdf(html, destino)
    return destino


def generar_pdf_recibo(base_dir: str, recibo: dict, cliente: dict) -> str:
    contexto = {
        "service": _service_context(base_dir),
        "cliente": cliente,
        "recibo": recibo,
        "blanco": False,
    }
    html = pdf_utils.render_html_template(
        current_app.config["DOC_TEMPLATES_DIR"], "recibo.html", contexto
    )
    fecha = _fecha_ddmmyyyy(recibo.get("fecha"))
    nombre_archivo = pdf_utils.nombre_pdf_recibo(fecha, cliente.get("nombre", ""), recibo.get("numero", ""))
    destino = os.path.join(current_app.config["DOCUMENTOS_DIR"], "recibos", nombre_archivo)
    pdf_utils.html_to_pdf(html, destino)
    return destino


def generar_pdf_blanco(base_dir: str, tipo: str) -> str:
    """Genera un boleto o recibo en blanco (sin datos de cliente y sin
    consumir numeración). `tipo` es 'boleto' o 'recibo'."""
    contexto = {
        "service": _service_context(base_dir),
        "cliente": {campo: "" for campo in models.CLIENTE_FIELDS},
        "blanco": True,
    }
    if tipo == "boleto":
        contexto["boleto"] = {campo: "" for campo in models.BOLETO_FIELDS}
        template_name = "boleto.html"
        nombre_default = "boleto_recepcion_en_blanco.pdf"
        subcarpeta = "boletos"
    else:
        contexto["recibo"] = {campo: "" for campo in models.RECIBO_FIELDS}
        template_name = "recibo.html"
        nombre_default = "recibo_en_blanco.pdf"
        subcarpeta = "recibos"

    html = pdf_utils.render_html_template(
        current_app.config["DOC_TEMPLATES_DIR"], template_name, contexto
    )
    destino = os.path.join(current_app.config["DOCUMENTOS_DIR"], "blancos", subcarpeta, nombre_default)
    destino = pdf_utils.unique_path(destino)
    pdf_utils.html_to_pdf(html, destino)
    return destino
