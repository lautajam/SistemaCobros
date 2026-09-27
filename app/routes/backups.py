import os
import shutil
import tempfile

from flask import Blueprint, after_this_request, current_app, flash, redirect, render_template, request, send_file, url_for

from .. import backup

bp = Blueprint("backups", __name__, url_prefix="/backups")


def _recortar(mensaje, largo=800):
    return mensaje if len(mensaje) <= largo else mensaje[:largo] + "…"


@bp.route("/")
def index():
    return render_template("backups/index.html")


@bp.route("/crear", methods=["POST"])
def crear():
    """Crea un backup y lo entrega como descarga normal del navegador. No queda
    copia en el servidor. Si falla, vuelve a la pantalla con el mensaje."""
    try:
        ruta = backup.crear_backup_para_descargar()
    except backup.BackupError as error:
        flash(_recortar(f"No se pudo crear el backup: {error}"), "error")
        return redirect(url_for("backups.index"))
    except Exception as error:
        current_app.logger.exception("Falló la creación del backup")
        flash(_recortar(f"No se pudo crear el backup: {error}"), "error")
        return redirect(url_for("backups.index"))

    respuesta = send_file(ruta, as_attachment=True, download_name=os.path.basename(ruta), mimetype="application/zip")
    # La pantalla usa esta marca para saber que la descarga ya empezó y volver a
    # habilitar el botón (no se puede saber de otra forma con una descarga normal).
    respuesta.set_cookie("backup_listo", request.form.get("marca", "")[:40], max_age=120, path="/backups", samesite="Lax")

    # send_file ya abrió el archivo: en Linux se puede borrar la carpeta temporal
    # ahora y la descarga se sigue enviando completa desde el archivo abierto.
    @after_this_request
    def _borrar_temporal(resp):
        shutil.rmtree(os.path.dirname(ruta), ignore_errors=True)
        return resp

    return respuesta


@bp.route("/subir", methods=["POST"])
def subir():
    archivo = request.files.get("archivo")
    if not archivo or not (archivo.filename or "").lower().endswith(".zip"):
        flash("Elegí un archivo de backup (.zip) para restaurar.", "error")
        return redirect(url_for("backups.index"))

    with tempfile.TemporaryDirectory() as tmpdir:
        temporal = os.path.join(tmpdir, "subido.zip")
        archivo.save(temporal)
        try:
            backup.restaurar_backup(temporal)
            flash("Backup restaurado correctamente. Los datos actuales fueron reemplazados por los del backup.", "success")
        except backup.BackupError as error:
            flash(_recortar(str(error)), "error")
        except Exception as error:
            current_app.logger.exception("Falló la restauración")
            flash(_recortar(f"No se pudo restaurar el backup: {error}"), "error")
    return redirect(url_for("backups.index"))
