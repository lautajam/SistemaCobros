"""
auditoria.py
------------
Un boleto o recibo emitido no se toca: solo el administrador puede editarlo (o
eliminarlo) y cada vez queda registrado en la base de datos —quién, cuándo y qué
cambió— y se muestra en la pantalla del documento. El PDF NO lleva ninguna marca.
"""

from flask_login import current_user
from sqlalchemy import select

from . import fechas, formatos, repo
from .db import Session
from .models import AuditoriaDocumento

ETIQUETAS = {
    "boleto": {
        "fecha": "Fecha", "hora": "Hora", "equipo": "Tipo de equipo", "marca": "Marca", "modelo": "Modelo",
        "numero_serie": "N.º de serie", "especificaciones": "Especificaciones", "accesorios": "Accesorios",
        "estado_fisico": "Estado físico", "problema": "Problema informado", "observaciones": "Observaciones",
    },
    "recibo": {
        "fecha": "Fecha", "equipo": "Tipo de equipo", "trabajo": "Trabajo", "descripcion": "Descripción",
        "importe": "Importe", "forma_pago": "Forma de pago", "observaciones": "Observaciones",
    },
}
ACCIONES = {"editado": "Editado", "eliminado": "Eliminado"}


def _texto(campo, valor):
    """Cómo se muestra un valor en el historial de cambios."""
    if campo == "importe":
        numero = repo._parse_importe(valor)
        return "(vacío)" if numero is None else "$ " + formatos.pesos(numero)
    if valor is None or str(valor).strip() == "":
        return "(vacío)"
    if campo == "fecha":
        return fechas.a_texto(valor)
    return str(valor).strip()


def _igual(campo, a, b):
    if campo == "importe":
        return repo._parse_importe(a) == repo._parse_importe(b)
    if campo == "fecha":
        return fechas.parsear(a) == fechas.parsear(b)
    return str(a or "").strip() == str(b or "").strip()


def diferencias(documento, antes, nuevos):
    """Campos que realmente cambian. `nuevos` solo trae los campos enviados.
    Devuelve (lista para el historial, dict {campo: valor_nuevo} para guardar)."""
    cambios, a_guardar = [], {}
    for campo, etiqueta in ETIQUETAS[documento].items():
        if campo not in nuevos or _igual(campo, antes.get(campo), nuevos[campo]):
            continue
        cambios.append({
            "campo": campo, "etiqueta": etiqueta,
            "antes": _texto(campo, antes.get(campo)), "despues": _texto(campo, nuevos[campo]),
        })
        a_guardar[campo] = nuevos[campo]
    return cambios, a_guardar


def registrar(documento, doc, accion, cambios):
    """Agrega la fila de auditoría a la sesión SIN confirmarla: se confirma junto con el
    cambio (o la eliminación) del documento, así nunca queda uno sin el otro."""
    Session.add(AuditoriaDocumento(
        documento=documento, documento_id=doc["id"], numero=doc.get("numero", ""), accion=accion,
        usuario_id=current_user.id, usuario_texto=f"{current_user.nombre_visible} ({current_user.usuario})",
        cambios=cambios,
    ))


def instantanea(documento, doc, cliente_nombre=""):
    """Datos del documento tal como estaban, para dejar constancia al eliminarlo."""
    filas = [{"campo": "cliente", "etiqueta": "Cliente", "antes": cliente_nombre or "(sin cliente)", "despues": ""}]
    for campo, etiqueta in ETIQUETAS[documento].items():
        if str(doc.get(campo) or "").strip():
            filas.append({"campo": campo, "etiqueta": etiqueta, "antes": _texto(campo, doc.get(campo)), "despues": ""})
    return filas


def historial(documento, documento_id):
    return list(Session.scalars(
        select(AuditoriaDocumento)
        .where(AuditoriaDocumento.documento == documento, AuditoriaDocumento.documento_id == documento_id)
        .order_by(AuditoriaDocumento.momento.desc(), AuditoriaDocumento.id.desc())
    ))


def ids_editados(documento):
    return set(Session.scalars(
        select(AuditoriaDocumento.documento_id)
        .where(AuditoriaDocumento.documento == documento, AuditoriaDocumento.accion == "editado")
    ))


def recientes(limite=300):
    return list(Session.scalars(
        select(AuditoriaDocumento).order_by(AuditoriaDocumento.momento.desc(), AuditoriaDocumento.id.desc()).limit(limite)
    ))
