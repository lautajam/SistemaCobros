"""
backup.py
---------
Backups y restauración completos de la aplicación.

Un backup es un .zip con:
  - db.dump        volcado de PostgreSQL (pg_dump, formato custom)
  - documentos/    todos los PDF generados
  - manifest.json  fecha, tipo, versión del esquema y cantidades

Los backups se guardan en la carpeta BACKUP_DIR, que docker-compose monta
desde una carpeta de la PC (fuera de Docker). Se crean:
  - a mano, con el botón de la pantalla Backups;
  - solos, cada BACKUP_INTERVAL_HOURS horas mientras la app está abierta
    (solo si hubo cambios desde el último);
  - al apagar el contenedor (ver gunicorn.conf.py -> on_exit).

Restaurar REEMPLAZA todos los datos actuales; antes de hacerlo se guarda un
backup "previo-restauracion" por seguridad.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from datetime import datetime

from flask import current_app
from sqlalchemy import text
from sqlalchemy.engine import make_url

from . import db

FORMAT_VERSION = 1
APP_ID = "service-app"

TIPOS = {
    "manual": "Manual",
    "auto": "Automático",
    "apagado": "Al apagar",
    "previo-restauracion": "Previo a restaurar",
}
# Solo estos tipos se borran solos cuando superan BACKUP_KEEP_AUTO.
TIPOS_ROTATIVOS = ("auto", "apagado")

_NOMBRE_RE = re.compile(r"^backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_([a-z-]+)\.zip$")

_lock = threading.RLock()
RESTORING = False


class BackupError(Exception):
    """Error esperable (con un mensaje entendible para mostrar al usuario)."""


def _cfg(clave):
    return current_app.config[clave]


def carpeta_backups():
    carpeta = _cfg("BACKUP_DIR")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


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
        # Suma de inserciones/modificaciones/borrados: sirve para saber si
        # hubo cambios desde el último backup.
        "actividad": int(_escalar(
            "SELECT COALESCE(SUM(n_tup_ins + n_tup_upd + n_tup_del), 0) FROM pg_stat_user_tables"
        )),
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


def crear_backup(tipo="manual"):
    """Crea un backup en la carpeta de backups y devuelve su nombre de archivo."""
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de backup desconocido: {tipo}")
    with _lock:
        carpeta = carpeta_backups()
        sello = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre = f"backup_{sello}_{tipo}.zip"
        destino = os.path.join(carpeta, nombre)
        temporal = destino + ".tmp"

        args, entorno = _conexion_pg()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                volcado = os.path.join(tmpdir, "db.dump")
                _ejecutar(
                    ["pg_dump", "-Fc", "--no-owner", "--no-privileges", *args, "-f", volcado],
                    entorno, "El volcado de la base de datos",
                )
                info = _info_db()
                with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(volcado, "db.dump")
                    info["documentos"] = _agregar_documentos(zf)
                    manifest = {
                        "app": APP_ID,
                        "format_version": FORMAT_VERSION,
                        "creado": datetime.now().isoformat(timespec="seconds"),
                        "tipo": tipo,
                        **info,
                    }
                    zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            os.replace(temporal, destino)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)

        _limpiar_rotativos()
        return nombre


def listar_backups():
    """Todos los .zip de la carpeta de backups, del más nuevo al más viejo."""
    carpeta = carpeta_backups()
    items = []
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        if not nombre.lower().endswith(".zip") or not os.path.isfile(ruta):
            continue
        estado = os.stat(ruta)
        coincide = _NOMBRE_RE.match(nombre)
        clave = coincide.group(1) if coincide else ""
        items.append({
            "nombre": nombre,
            "clave": clave,
            "tipo": TIPOS.get(clave, "Otro"),
            "fecha": datetime.fromtimestamp(estado.st_mtime),
            "bytes": estado.st_size,
        })
    items.sort(key=lambda i: i["fecha"], reverse=True)
    return items


def ruta_backup(nombre):
    """Ruta completa de un backup de la carpeta, validando el nombre para que
    no se pueda salir de ella."""
    if not nombre or "/" in nombre or "\\" in nombre or not nombre.lower().endswith(".zip"):
        raise BackupError("Nombre de backup inválido.")
    ruta = os.path.join(carpeta_backups(), nombre)
    if not os.path.isfile(ruta):
        raise BackupError("Ese backup ya no existe en la carpeta.")
    return ruta


def _limpiar_rotativos():
    conservar = _cfg("BACKUP_KEEP_AUTO")
    if conservar <= 0:
        return
    rotativos = [b for b in listar_backups() if b["clave"] in TIPOS_ROTATIVOS]
    for viejo in rotativos[conservar:]:
        try:
            os.remove(os.path.join(carpeta_backups(), viejo["nombre"]))
        except OSError:
            pass


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
    if not zipfile.is_zipfile(ruta):
        raise BackupError("El archivo no es un .zip válido.")
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
    """Reemplaza TODOS los datos actuales por los del backup."""
    global RESTORING
    with _lock:
        _validar_zip(ruta_zip)
        RESTORING = True
        try:
            try:
                crear_backup("previo-restauracion")
            except BackupError as error:
                raise BackupError(
                    f"No se restauró nada: no se pudo guardar el backup de seguridad previo. {error}"
                )
            db.dispose()
            args, entorno = _conexion_pg()
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(ruta_zip) as zf:
                    zf.extract("db.dump", tmpdir)
                    _ejecutar(
                        [
                            "pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges",
                            "--single-transaction", "--exit-on-error", *args,
                            os.path.join(tmpdir, "db.dump"),
                        ],
                        entorno, "La restauración de la base de datos",
                    )
                    _restaurar_documentos(zf)
            _migrar_a_ultima()
        finally:
            RESTORING = False
            db.dispose()


# ---------------------------------------------------------------- automáticos

def _hay_cambios_desde_el_ultimo():
    ultimos = listar_backups()
    if not ultimos:
        return True
    try:
        with zipfile.ZipFile(os.path.join(carpeta_backups(), ultimos[0]["nombre"])) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        return manifest.get("actividad") != _info_db()["actividad"]
    except Exception:
        return True


def _corresponde_backup_automatico(intervalo_horas):
    ultimos = listar_backups()
    if ultimos and (datetime.now() - ultimos[0]["fecha"]).total_seconds() < intervalo_horas * 3600:
        return False
    return _hay_cambios_desde_el_ultimo()


def start_scheduler(app):
    """Hilo en segundo plano que hace un backup automático cada
    BACKUP_INTERVAL_HOURS horas (0 = desactivado), si hubo cambios."""
    intervalo = app.config["BACKUP_INTERVAL_HOURS"]
    if intervalo <= 0:
        return

    def bucle():
        while True:
            time.sleep(60)
            try:
                with app.app_context():
                    if not RESTORING and _corresponde_backup_automatico(intervalo):
                        nombre = crear_backup("auto")
                        app.logger.info("Backup automático creado: %s", nombre)
            except Exception:
                app.logger.exception("Falló el backup automático")

    threading.Thread(target=bucle, daemon=True, name="backup-automatico").start()


def backup_al_apagar():
    """Lo llama gunicorn (on_exit) cuando el contenedor se está por apagar."""
    from . import create_app

    app = create_app(start_scheduler=False)
    with app.app_context():
        return crear_backup("apagado")
