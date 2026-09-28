"""
documentos.py
-------------
Une los datos (cliente/boleto/recibo/configuración del service) con las
plantillas HTML editables de `templates/` y genera el PDF final en la
carpeta que corresponde, con el nombre de archivo obligatorio.
"""

import base64
import os
from datetime import datetime

from flask import current_app

from . import fechas, models, pdf_utils, repo


def _fecha_ddmmyyyy(fecha_iso: str) -> str:
    """Convierte una fecha 'YYYY-MM-DD' (la que produce <input type=date>)
    al formato DD-MM-YYYY exigido para los nombres de archivo."""
    if fecha_iso:
        try:
            return datetime.strptime(fecha_iso, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            pass
    return datetime.now().strftime("%d-%m-%Y")


def _service_context() -> dict:
    # Import diferido para evitar import circular con el blueprint.
    from .routes.configuracion import get_config, get_logo

    cfg = get_config()
    logo_path = ""
    logo = get_logo()
    if logo:
        contenido, mime = logo
        logo_path = f"data:{mime};base64,{base64.b64encode(contenido).decode('ascii')}"
    return {**cfg, "logo_path": logo_path}


def _carpeta(tipo: str) -> str:
    return os.path.join(current_app.config["DOCUMENTOS_DIR"], "boletos" if tipo == "boleto" else "recibos")


def _modelo(tipo: str):
    return models.Boleto if tipo == "boleto" else models.Recibo


def _nombre_esperado(tipo: str, doc: dict, cliente: dict) -> str:
    fecha = _fecha_ddmmyyyy(doc.get("fecha"))
    if tipo == "boleto":
        return pdf_utils.nombre_pdf_boleto(fecha, cliente.get("nombre", ""), doc.get("numero", ""))
    return pdf_utils.nombre_pdf_recibo(fecha, cliente.get("nombre", ""), doc.get("numero", ""))


def _pdf_actual(tipo: str, doc: dict, cliente: dict):
    """Ruta del PDF emitido de este documento, o None si no existe.
    Usa el nombre guardado en la base; en documentos anteriores a ese registro lo busca
    por número (los números no se reutilizan) y lo anota."""
    carpeta = _carpeta(tipo)
    guardado = doc.get("pdf_archivo") or ""
    if guardado and os.path.isfile(os.path.join(carpeta, guardado)):
        return os.path.join(carpeta, guardado)
    prefijo = "boleto_recepcion_" if tipo == "boleto" else "recibo_"
    candidatos = [
        os.path.join(carpeta, n) for n in (os.listdir(carpeta) if os.path.isdir(carpeta) else [])
        if n.startswith(prefijo) and n.endswith(f"_{doc.get('numero', '')}.pdf")
    ]
    if not candidatos:
        return None
    esperado = os.path.join(carpeta, _nombre_esperado(tipo, doc, cliente))
    elegido = esperado if esperado in candidatos else max(candidatos, key=os.path.getmtime)
    repo.actualizar(_modelo(tipo), doc["id"], {"pdf_archivo": os.path.basename(elegido)})
    return elegido


def pdf_emitido(tipo: str, doc: dict, cliente: dict) -> str:
    """El PDF que se entregó al cliente, tal cual. Solo se genera si nunca existió
    (por ejemplo, si falló al crear el documento): así abrir el PDF no cambia nada
    aunque después se edite el cliente."""
    existente = _pdf_actual(tipo, doc, cliente)
    if existente:
        return existente
    return generar_pdf_boleto(doc, cliente) if tipo == "boleto" else generar_pdf_recibo(doc, cliente)


def regenerar_pdf(tipo: str, doc: dict, cliente: dict) -> str:
    """Solo para cuando un administrador edita el documento: genera el PDF nuevo y
    recién entonces borra el anterior (si falla, el anterior queda)."""
    anterior = _pdf_actual(tipo, doc, cliente)
    nuevo = generar_pdf_boleto(doc, cliente) if tipo == "boleto" else generar_pdf_recibo(doc, cliente)
    if anterior and os.path.abspath(anterior) != os.path.abspath(nuevo) and os.path.isfile(anterior):
        os.remove(anterior)
    return nuevo


def _guardar_pdf(tipo: str, doc: dict, destino: str) -> None:
    doc["pdf_archivo"] = os.path.basename(destino)
    repo.actualizar(_modelo(tipo), doc["id"], {"pdf_archivo": doc["pdf_archivo"]})


def generar_pdf_boleto(boleto: dict, cliente: dict) -> str:
    contexto = {
        "service": _service_context(),
        "cliente": cliente,
        "boleto": {**boleto, "fecha": fechas.a_texto(boleto.get("fecha"))},
        "blanco": False,
    }
    html = pdf_utils.render_html_template(
        current_app.config["DOC_TEMPLATES_DIR"], "boleto.html", contexto
    )
    fecha = _fecha_ddmmyyyy(boleto.get("fecha"))
    nombre_archivo = pdf_utils.nombre_pdf_boleto(fecha, cliente.get("nombre", ""), boleto.get("numero", ""))
    destino = os.path.join(current_app.config["DOCUMENTOS_DIR"], "boletos", nombre_archivo)
    pdf_utils.html_to_pdf(html, destino)
    _guardar_pdf("boleto", boleto, destino)
    return destino


def generar_pdf_recibo(recibo: dict, cliente: dict) -> str:
    contexto = {
        "service": _service_context(),
        "cliente": cliente,
        "recibo": {**recibo, "fecha": fechas.a_texto(recibo.get("fecha"))},
        "blanco": False,
    }
    html = pdf_utils.render_html_template(
        current_app.config["DOC_TEMPLATES_DIR"], "recibo.html", contexto
    )
    fecha = _fecha_ddmmyyyy(recibo.get("fecha"))
    nombre_archivo = pdf_utils.nombre_pdf_recibo(fecha, cliente.get("nombre", ""), recibo.get("numero", ""))
    destino = os.path.join(current_app.config["DOCUMENTOS_DIR"], "recibos", nombre_archivo)
    pdf_utils.html_to_pdf(html, destino)
    _guardar_pdf("recibo", recibo, destino)
    return destino


def generar_pdf_tarifario(grupos: list) -> str:
    """El tarifario no es un documento emitido: siempre se regenera con los precios
    vigentes y se guarda en un único archivo (se pisa cada vez, sin acumular versiones)."""
    contexto = {"service": _service_context(), "grupos": grupos, "hoy": fechas.hoy_texto(), "COMPLEJIDADES": models.COMPLEJIDADES}
    html = pdf_utils.render_html_template(current_app.config["DOC_TEMPLATES_DIR"], "tarifario.html", contexto)
    destino = os.path.join(current_app.config["DOCUMENTOS_DIR"], "tarifario", "tarifario.pdf")
    pdf_utils.html_to_pdf(html, destino)
    return destino


def generar_pdf_blanco(tipo: str) -> str:
    """Genera un boleto o recibo en blanco (sin datos de cliente y sin
    consumir numeración). `tipo` es 'boleto' o 'recibo'."""
    contexto = {
        "service": _service_context(),
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
