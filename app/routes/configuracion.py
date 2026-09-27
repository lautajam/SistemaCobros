import os

from flask import Blueprint, current_app, redirect, render_template, request, send_from_directory, url_for

from .. import csv_utils, models

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

EXTENSIONES_LOGO_PERMITIDAS = {".png", ".jpg", ".jpeg", ".gif"}


def _logo_dir(base_dir):
    directorio = os.path.join(base_dir, "data", "configuracion", "logo")
    os.makedirs(directorio, exist_ok=True)
    return directorio


def get_config(base_dir, path=None):
    """Lee la configuración del service. Si todavía no se configuró nada,
    devuelve valores por defecto (nunca falla ni lanza excepción)."""
    path = path or os.path.join(base_dir, "data", "configuracion", "configuracion.csv")
    csv_utils.ensure_csv(path, models.CONFIG_FIELDS)
    filas = csv_utils.read_all(path, models.CONFIG_FIELDS)
    cfg = dict(VALORES_POR_DEFECTO)
    if filas:
        cfg.update({k: v for k, v in filas[0].items() if v})
    return cfg


@bp.route("/", methods=["GET", "POST"])
def form():
    base_dir = current_app.config["BASE_DIR"]
    path = current_app.config["CONFIG_CSV"]
    cfg = get_config(base_dir, path)

    if request.method == "POST":
        nueva_cfg = {
            "nombre": (request.form.get("nombre") or "").strip(),
            "cuit": (request.form.get("cuit") or "").strip(),
            "telefono": (request.form.get("telefono") or "").strip(),
            "email": (request.form.get("email") or "").strip(),
            "direccion": (request.form.get("direccion") or "").strip(),
            "localidad": (request.form.get("localidad") or "").strip(),
            "codigo_postal": (request.form.get("codigo_postal") or "").strip(),
            "logo": cfg.get("logo", ""),
        }
        archivo = request.files.get("logo_file")
        if archivo and archivo.filename:
            ext = os.path.splitext(archivo.filename)[1].lower()
            if ext in EXTENSIONES_LOGO_PERMITIDAS:
                nombre_logo = f"logo{ext}"
                archivo.save(os.path.join(_logo_dir(base_dir), nombre_logo))
                nueva_cfg["logo"] = nombre_logo
        csv_utils.write_all(path, models.CONFIG_FIELDS, [nueva_cfg])
        return redirect(url_for("configuracion.form"))

    return render_template("configuracion/form.html", cfg=cfg)


@bp.route("/logo")
def logo():
    base_dir = current_app.config["BASE_DIR"]
    cfg = get_config(base_dir, current_app.config["CONFIG_CSV"])
    if not cfg.get("logo"):
        return "", 404
    return send_from_directory(_logo_dir(base_dir), cfg["logo"])
