"""
csv_utils.py
------------
Capa de acceso a datos basada exclusivamente en archivos CSV (UTF-8).

Reglas que respeta este módulo (ver requisito 22 del pedido original):
- Nunca sobrescribe accidentalmente información: toda escritura se hace en un
  archivo temporal y luego se reemplaza de forma atómica (os.replace).
- Mantiene siempre los encabezados (fieldnames) del CSV.
- Usa el módulo estándar `csv`, que escapa correctamente comas, comillas y
  saltos de línea dentro de los campos.
- Crea automáticamente carpetas y archivos si todavía no existen.
- Usa un lock en memoria por archivo para evitar condiciones de carrera
  cuando el servidor de desarrollo atiende varias peticiones a la vez.
"""

import csv
import os
import tempfile
import threading

_locks = {}
_locks_guard = threading.Lock()


def _lock_for(path):
    """Devuelve (y crea si hace falta) un Lock exclusivo para `path`."""
    with _locks_guard:
        lock = _locks.get(path)
        if lock is None:
            lock = threading.Lock()
            _locks[path] = lock
        return lock


def ensure_csv(path, fieldnames):
    """Crea el CSV con sus encabezados si todavía no existe."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if os.path.exists(path):
        return
    with _lock_for(path):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()


def read_all(path, fieldnames):
    """Lee todas las filas del CSV como lista de dicts."""
    ensure_csv(path, fieldnames)
    with _lock_for(path):
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            filas = []
            for fila in reader:
                # Normaliza para que siempre existan todas las columnas
                # esperadas, aunque el archivo tenga columnas de más o de menos.
                filas.append({clave: (fila.get(clave) or "") for clave in fieldnames})
            return filas


def write_all(path, fieldnames, filas):
    """Sobrescribe el CSV completo de forma atómica."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    with _lock_for(path):
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=directory)
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
                writer.writeheader()
                for fila in filas:
                    writer.writerow({clave: fila.get(clave, "") for clave in fieldnames})
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise


def append_row(path, fieldnames, fila):
    """Agrega una fila nueva al final del CSV (reescritura atómica completa)."""
    filas = read_all(path, fieldnames)
    filas.append(fila)
    write_all(path, fieldnames, filas)
    return fila


def update_row(path, fieldnames, campo_id, valor_id, cambios):
    """Actualiza la primera fila cuyo `campo_id` coincida con `valor_id`."""
    filas = read_all(path, fieldnames)
    encontrado = False
    for fila in filas:
        if fila.get(campo_id) == valor_id:
            fila.update(cambios)
            encontrado = True
            break
    if encontrado:
        write_all(path, fieldnames, filas)
    return encontrado


def delete_row(path, fieldnames, campo_id, valor_id):
    """Elimina la fila con ese id. El número/id eliminado nunca se reutiliza
    porque los contadores (ver counters.py) son independientes del contenido
    de este archivo."""
    filas = read_all(path, fieldnames)
    nuevas = [f for f in filas if f.get(campo_id) != valor_id]
    borrado = len(nuevas) != len(filas)
    if borrado:
        write_all(path, fieldnames, nuevas)
    return borrado


def get_row(path, fieldnames, campo_id, valor_id):
    """Devuelve la primera fila con ese id, o None."""
    for fila in read_all(path, fieldnames):
        if fila.get(campo_id) == valor_id:
            return fila
    return None
