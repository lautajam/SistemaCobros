import os

from flask import Blueprint, Response, redirect, render_template, request, url_for

from ..auth import permiso
from ..db import Session
from ..models import Configuracion

bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")

VALORES_POR_DEFECTO = {
    "nombre": "Mi Service Técnico",
    "cuit": "",
    "telefono": "",
    "email": "",
    "direccion": "",
    "localidad": "",
    "codigo_postal": "",
    "logo": "",
}

CAMPOS_TEXTO = ["nombre", "cuit", "telefono", "email", "direccion", "localidad", "codigo_postal"]

TIPOS_LOGO = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
}

TAMANO_MAXIMO_LOGO = 2 * 1024 * 1024


def get_config():
    """Lee la configuración del service. Si todavía no se configuró nada,
    devuelve valores por defecto (nunca falla ni lanza excepción)."""
    cfg = dict(VALORES_POR_DEFECTO)
    fila = Session.get(Configuracion, 1)
    if fila:
        datos = fila.to_dict()
        cfg.update({k: v for k, v in datos.items() if v and k in VALORES_POR_DEFECTO})
    return cfg


def get_logo():
    """Devuelve (bytes, mime) del logo cargado, o None si no hay."""
    fila = Session.get(Configuracion, 1)
    if fila and fila.logo_data:
        return fila.logo_data, fila.logo_mime or "image/png"
    return None


@bp.route("/", methods=["GET", "POST"])
@permiso("configuracion:gestionar")
def form():
    if request.method == "POST":
        fila = Session.get(Configuracion, 1) or Configuracion(id=1)
        for campo in CAMPOS_TEXTO:
            setattr(fila, campo, (request.form.get(campo) or "").strip())
        archivo = request.files.get("logo_file")
        if archivo and archivo.filename:
            ext = os.path.splitext(archivo.filename)[1].lower()
            contenido = archivo.read(TAMANO_MAXIMO_LOGO + 1)
            if ext in TIPOS_LOGO and 0 < len(contenido) <= TAMANO_MAXIMO_LOGO:
                fila.logo = f"logo{ext}"
                fila.logo_mime = TIPOS_LOGO[ext]
                fila.logo_data = contenido
        Session.add(fila)
        Session.commit()
        return redirect(url_for("configuracion.form"))

    return render_template("configuracion/form.html", cfg=get_config())


@bp.route("/logo")
@permiso("configuracion:gestionar")
def logo():
    datos = get_logo()
    if not datos:
        return "", 404
    contenido, mime = datos
    return Response(contenido, mimetype=mime)
