import math

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from werkzeug.security import check_password_hash

from .. import auth
from ..db import Session
from ..models import Usuario

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    destino = request.values.get("next", "")
    if current_user.is_authenticated:
        return redirect(destino if auth.es_destino_seguro(destino) else url_for("main.index"))

    error = None
    estado = 200
    usuario_txt = ""

    if request.method == "POST":
        usuario_txt = auth.normalizar_usuario(request.form.get("usuario"))
        clave = request.form.get("password") or ""
        ip = request.remote_addr or ""

        espera = auth.segundos_de_bloqueo(usuario_txt, ip)
        if espera:
            minutos = max(1, math.ceil(espera / 60))
            error = f"Demasiados intentos fallidos. Probá de nuevo en {minutos} min."
            estado = 429
        else:
            usuario = Session.scalar(select(Usuario).where(Usuario.usuario == usuario_txt)) if usuario_txt else None
            # Con usuario inexistente se compara igual contra un hash falso: tarda lo mismo.
            clave_ok = check_password_hash(usuario.password_hash if usuario else auth._HASH_FALSO, clave)
            if usuario is not None and clave_ok and usuario.activo:
                auth.iniciar_sesion(usuario)
                if usuario.debe_cambiar_password:
                    return redirect(url_for("cuenta.index"))
                return redirect(destino if auth.es_destino_seguro(destino) else url_for("main.index"))
            auth.registrar_fallo(usuario_txt, ip)
            error = "Usuario o contraseña incorrectos."
            estado = 401

    return render_template("auth/login.html", error=error, usuario=usuario_txt, next=destino), estado


@bp.route("/logout", methods=["POST"])
def logout():
    auth.cerrar_sesion_actual()
    flash("Cerraste sesión.", "success")
    return redirect(url_for("auth.login"))
