"""
counters.py
-----------
Numeración correlativa, persistente e independiente por tipo de documento.

Requisito clave (punto 8 del pedido): nunca reutilizar un número, aunque se
elimine el registro correspondiente. Por eso el contador se guarda en su
propio CSV (`data/configuracion/contadores.csv`) y solo se incrementa, nunca
se recalcula a partir de `len(registros)`.
"""

import os

from . import csv_utils

FIELDNAMES = ["tipo", "ultimo_numero"]
TIPOS = ["cliente", "boleto", "recibo"]


def _path(base_dir):
    return os.path.join(base_dir, "data", "configuracion", "contadores.csv")


def ensure_counters(base_dir):
    """Garantiza que existan las tres filas de contadores (cliente/boleto/recibo)."""
    path = _path(base_dir)
    csv_utils.ensure_csv(path, FIELDNAMES)
    filas = csv_utils.read_all(path, FIELDNAMES)
    existentes = {f["tipo"] for f in filas}
    faltan = [t for t in TIPOS if t not in existentes]
    if faltan:
        for tipo in faltan:
            filas.append({"tipo": tipo, "ultimo_numero": "0"})
        csv_utils.write_all(path, FIELDNAMES, filas)


def get_last_number(base_dir, tipo):
    """Último número emitido para `tipo` (para mostrar en el dashboard)."""
    ensure_counters(base_dir)
    fila = csv_utils.get_row(_path(base_dir), FIELDNAMES, "tipo", tipo)
    if not fila or not fila.get("ultimo_numero"):
        return 0
    try:
        return int(fila["ultimo_numero"])
    except ValueError:
        return 0


def next_number(base_dir, tipo):
    """Incrementa de forma atómica el contador de `tipo` y devuelve el nuevo
    número (int). Este número jamás se reutiliza, incluso si luego se borra
    el boleto/recibo/cliente que lo usó."""
    path = _path(base_dir)
    ensure_counters(base_dir)
    # Lock adicional para que todo el ciclo leer -> incrementar -> escribir
    # sea atómico, incluso con varias peticiones concurrentes.
    lock = csv_utils._lock_for(path + "::next_number")
    with lock:
        filas = csv_utils.read_all(path, FIELDNAMES)
        nuevo = None
        encontrado = False
        for fila in filas:
            if fila["tipo"] == tipo:
                actual = int(fila["ultimo_numero"]) if fila["ultimo_numero"] else 0
                nuevo = actual + 1
                fila["ultimo_numero"] = str(nuevo)
                encontrado = True
                break
        if not encontrado:
            nuevo = 1
            filas.append({"tipo": tipo, "ultimo_numero": "1"})
        csv_utils.write_all(path, FIELDNAMES, filas)
        return nuevo
