"""
backup.py
---------
Backups y restauración completos de la aplicación. Todo es manual: solo se
hace un backup cuando el usuario lo pide desde la pantalla Backups.

Un backup es un .zip con:
  - db.dump        volcado de PostgreSQL (pg_dump, formato custom)
  - documentos/    todos los PDF generados
  - manifest.json  fecha, versión del esquema y cantidades

El .zip se arma en una carpeta temporal y se entrega como descarga: no queda
ninguna copia dentro de Docker. Restaurar REEMPLAZA todos los datos actuales.
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from datetime import datetime

from flask import current_app
from sqlalchemy import text
from sqlalchemy.engine import make_url

from . import db

FORMAT_VERSION = 1
APP_ID = "service-app"

_lock = threading.Lock()
RESTORING = False


class BackupError(Exception):
    """Error esperable (con un mensaje entendible para mostrar al usuario)."""


def _cfg(clave):
    return current_app.config[clave]


def _conexion_pg():
    url = make_url(_cfg("DATABASE_URL"))
    entorno = dict(os.environ)
    if url.password:
        entorno["PGPASSWORD"] = url.password
    args = ["-h", url.host or "localhost", "-p", str(url.port or 5432), "-U", url.username, "-d", url.database]
    return args, entorno


def _ejecutar(comando, entorno, que):
    try:
        r = subprocess.run(comando, env=entorno, capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        raise BackupError(f"No se encontró el programa '{comando[0]}' dentro del contenedor.")
    except subprocess.TimeoutExpired:
        raise BackupError(f"{que} tardó demasiado y se canceló.")
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout or "").strip()
        raise BackupError(f"{que} falló: {detalle}")


def _escalar(sql):
    with db.get_engine().connect() as conexion:
        return conexion.execute(text(sql)).scalar()


def _info_db():
    return {
        "alembic_revision": _escalar("SELECT version_num FROM alembic_version"),
        "clientes": _escalar("SELECT COUNT(*) FROM clientes"),
        "boletos": _escalar("SELECT COUNT(*) FROM boletos"),
        "recibos": _escalar("SELECT COUNT(*) FROM recibos"),
    }


def _agregar_documentos(zf):
    base = _cfg("DOCUMENTOS_DIR")
    cantidad = 0
    for raiz, _dirs, archivos in os.walk(base):
        for archivo in archivos:
            if not archivo.lower().endswith(".pdf"):
                continue
            ruta = os.path.join(raiz, archivo)
            relativa = os.path.relpath(ruta, base).replace(os.sep, "/")
            zf.write(ruta, f"documentos/{relativa}")
            cantidad += 1
    return cantidad


def crear_backup_para_descargar():
    """Crea el backup en una carpeta temporal y devuelve la ruta del .zip. Quien
    lo use debe borrar después esa carpeta (os.path.dirname de la ruta)."""
    with _lock:
        carpeta = tempfile.mkdtemp(prefix="backup_descarga_")
        try:
            destino = os.path.join(carpeta, f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip")
            args, entorno = _conexion_pg()
            volcado = os.path.join(carpeta, "db.dump")
            _ejecutar(
                [
                    "pg_dump", "-Fc", "--no-owner", "--no-privileges",
                    # Estas tablas se crean vacías: un backup no debe traer sesiones abiertas
                    # (que "revivirían" al restaurar) ni la clave secreta ni intentos de ingreso.
                    "--exclude-table-data=sesiones", "--exclude-table-data=intentos_login", "--exclude-table-data=ajustes",
                    *args, "-f", volcado,
                ],
                entorno, "El volcado de la base de datos",
            )
            info = _info_db()
            with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(volcado, "db.dump")
                info["documentos"] = _agregar_documentos(zf)
                manifest = {
                    "app": APP_ID,
                    "format_version": FORMAT_VERSION,
                    "creado": datetime.now().isoformat(timespec="seconds"),
                    **info,
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            os.remove(volcado)
        except Exception:
            shutil.rmtree(carpeta, ignore_errors=True)
            raise
        return destino


# --------------------------------------------------------------- restauración

def _alembic_config():
    from alembic.config import Config

    base_dir = _cfg("BASE_DIR")
    cfg = Config(os.path.join(base_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(base_dir, "migrations"))
    return cfg


def _migrar_a_ultima():
    from alembic import command

    command.upgrade(_alembic_config(), "head")


def _validar_zip(ruta):
    if os.path.getsize(ruta) == 0:
        raise BackupError(
            "El archivo está vacío (0 bytes): la descarga del backup no se completó. "
            "Creá un backup nuevo y usá ese archivo."
        )
    if not zipfile.is_zipfile(ruta):
        raise BackupError("El archivo no es un .zip válido (puede estar incompleto o dañado).")
    with zipfile.ZipFile(ruta) as zf:
        nombres = zf.namelist()
        if "manifest.json" not in nombres or "db.dump" not in nombres:
            raise BackupError("El archivo no es un backup de esta aplicación (faltan archivos).")
        try:
            manifest = json.loads(zf.read("manifest.json"))
        except ValueError:
            raise BackupError("El backup está dañado (manifest.json ilegible).")
        if manifest.get("app") != APP_ID or manifest.get("format_version", 0) > FORMAT_VERSION:
            raise BackupError("El archivo no es un backup compatible con esta versión de la aplicación.")
        for nombre in nombres:
            if nombre in ("manifest.json", "db.dump"):
                continue
            partes = nombre.split("/")
            if partes[0] != "documentos" or ".." in partes or nombre.startswith("/"):
                raise BackupError("El backup contiene archivos inesperados.")
            if not nombre.endswith("/") and not nombre.lower().endswith(".pdf"):
                raise BackupError("El backup contiene archivos inesperados.")

    from alembic.script import ScriptDirectory

    conocidas = {s.revision for s in ScriptDirectory.from_config(_alembic_config()).walk_revisions()}
    revision = manifest.get("alembic_revision")
    if revision and revision not in conocidas:
        raise BackupError(
            "Este backup fue creado con una versión más nueva de la aplicación. "
            "Actualizá la aplicación antes de restaurarlo."
        )
    return manifest


def _restaurar_documentos(zf):
    base = os.path.realpath(_cfg("DOCUMENTOS_DIR"))
    for raiz, _dirs, archivos in os.walk(base):
        for archivo in archivos:
            if archivo.lower().endswith(".pdf"):
                os.remove(os.path.join(raiz, archivo))
    for nombre in zf.namelist():
        if not nombre.startswith("documentos/") or nombre.endswith("/"):
            continue
        destino = os.path.realpath(os.path.join(base, *nombre.split("/")[1:]))
        if not destino.startswith(base + os.sep):
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with zf.open(nombre) as origen, open(destino, "wb") as salida:
            shutil.copyfileobj(origen, salida)


def restaurar_backup(ruta_zip):
    """Reemplaza TODOS los datos actuales por los del backup. La base se
    restaura en una sola transacción: si falla, queda como estaba."""
    global RESTORING
    with _lock:
        _validar_zip(ruta_zip)
        RESTORING = True
        try:
            db.dispose()
            args, entorno = _conexion_pg()
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(ruta_zip) as zf:
                    zf.extract("db.dump", tmpdir)
                    datos_sql = os.path.join(tmpdir, "datos.sql")
                    guion = os.path.join(tmpdir, "restaurar.sql")
                    _ejecutar(
                        ["pg_restore", "--no-owner", "--no-privileges", "-f", datos_sql, os.path.join(tmpdir, "db.dump")],
                        entorno, "La lectura del backup",
                    )
                    # Todo en UNA transacción: se borra el esquema completo y se carga el del
                    # backup. Así no quedan tablas de la versión actual que el backup no tenga
                    # (por ejemplo, usuarios si el backup es anterior al login), y si algo
                    # falla no se toca nada.
                    with open(guion, "w", encoding="utf-8") as salida, open(datos_sql, encoding="utf-8") as origen:
                        salida.write("DROP SCHEMA public CASCADE;\nCREATE SCHEMA public;\n")
                        shutil.copyfileobj(origen, salida)
                    _ejecutar(
                        ["psql", "-q", "-v", "ON_ERROR_STOP=1", "--single-transaction", *args, "-f", guion],
                        entorno, "La restauración de la base de datos",
                    )
                    _restaurar_documentos(zf)
            _migrar_a_ultima()
            # Un backup anterior al login no trae usuarios: se vuelve a crear el admin inicial.
            from . import auth

            auth.asegurar_admin_inicial()
        finally:
            RESTORING = False
            db.dispose()
