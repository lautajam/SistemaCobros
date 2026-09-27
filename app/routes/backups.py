import os
import tempfile

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for

from .. import backup

bp = Blueprint("backups", __name__, url_prefix="/backups")

CONFIRMACION = "RESTAURAR"


def _recortar(mensaje, largo=800):
    return mensaje if len(mensaje) <= largo else mensaje[:largo] + "…"


def _confirmado():
    if (request.form.get("confirmacion") or "").strip() == CONFIRMACION:
        return True
    flash(f"No se restauró nada: para confirmar hay que escribir {CONFIRMACION}.")
    return False


def _restaurar(ruta):
    try:
        backup.restaurar_backup(ruta)
        flash("Backup restaurado correctamente. Todos los datos actuales fueron reemplazados por los del backup.")
    except backup.BackupError as error:
        flash(_recortar(str(error)))
    except Exception as error:
        current_app.logger.exception("Falló la restauración")
        flash(_recortar(f"No se pudo restaurar el backup: {error}"))


@bp.route("/")
def index():
    return render_template(
        "backups/index.html",
        backups=backup.listar_backups(),
        intervalo=current_app.config["BACKUP_INTERVAL_HOURS"],
        conservar=current_app.config["BACKUP_KEEP_AUTO"],
    )


@bp.route("/crear", methods=["POST"])
def crear():
    try:
        nombre = backup.crear_backup("manual")
        flash(f"Backup creado: {nombre}")
    except backup.BackupError as error:
        flash(_recortar(f"No se pudo crear el backup: {error}"))
    return redirect(url_for("backups.index"))


@bp.route("/descargar/<nombre>")
def descargar(nombre):
    try:
        ruta = backup.ruta_backup(nombre)
    except backup.BackupError as error:
        flash(str(error))
        return redirect(url_for("backups.index"))
    return send_file(ruta, as_attachment=True, download_name=nombre)


@bp.route("/restaurar/<nombre>", methods=["POST"])
def restaurar(nombre):
    if _confirmado():
        try:
            _restaurar(backup.ruta_backup(nombre))
        except backup.BackupError as error:
            flash(str(error))
    return redirect(url_for("backups.index"))


@bp.route("/subir", methods=["POST"])
def subir():
    if not _confirmado():
        return redirect(url_for("backups.index"))
    archivo = request.files.get("archivo")
    if not archivo or not (archivo.filename or "").lower().endswith(".zip"):
        flash("Elegí un archivo de backup (.zip) para restaurar.")
        return redirect(url_for("backups.index"))
    with tempfile.TemporaryDirectory() as tmpdir:
        temporal = os.path.join(tmpdir, "subido.zip")
        archivo.save(temporal)
        _restaurar(temporal)
    return redirect(url_for("backups.index"))
