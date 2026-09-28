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
    "cliente": {
        "nombre": "Nombre", "dni_cuit": "DNI / CUIT", "telefono": "Teléfono", "email": "Email",
        "direccion": "Dirección", "localidad": "Localidad", "codigo_postal": "Código postal",
        "observaciones": "Observaciones", "activo": "Estado",
    },
}
DOCUMENTOS = {"boleto": "Boleto", "recibo": "Recibo", "cliente": "Cliente"}
ACCIONES = {"editado": "Editado", "eliminado": "Eliminado"}


def _texto(campo, valor):
    """Cómo se muestra un valor en el historial de cambios."""
    if campo == "importe":
        numero = repo._parse_importe(valor)
        return "(vacío)" if numero is None else "$ " + formatos.pesos(numero)
    if campo == "activo":
        return "Habilitado" if valor else "Deshabilitado"
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
    if campo == "activo":
        return bool(a) == bool(b)
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
    """Datos del documento tal como estaban, para dejar constancia al eliminarlo.
    `cliente_nombre` es el dueño del boleto/recibo; un cliente no tiene uno (ya figura
    como "Nombre" en sus propios campos)."""
    filas = [{"campo": "cliente", "etiqueta": "Cliente", "antes": cliente_nombre or "(sin cliente)", "despues": ""}] if cliente_nombre or documento != "cliente" else []
    for campo, etiqueta in ETIQUETAS[documento].items():
        valor = doc.get(campo)
        if isinstance(valor, bool) or str(valor or "").strip():
            filas.append({"campo": campo, "etiqueta": etiqueta, "antes": _texto(campo, valor), "despues": ""})
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


def recientes(documento=None, usuario_id=None, limite=300):
    """Lista para la pantalla de Auditoría, con filtro opcional por tipo de documento
    y/o por quién hizo el cambio."""
    consulta = select(AuditoriaDocumento)
    if documento:
        consulta = consulta.where(AuditoriaDocumento.documento == documento)
    if usuario_id:
        consulta = consulta.where(AuditoriaDocumento.usuario_id == usuario_id)
    consulta = consulta.order_by(AuditoriaDocumento.momento.desc(), AuditoriaDocumento.id.desc()).limit(limite)
    return list(Session.scalars(consulta))
