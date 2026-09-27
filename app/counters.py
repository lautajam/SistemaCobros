"""
counters.py
-----------
Numeración correlativa, persistente e independiente por tipo de documento.

Requisito clave: nunca reutilizar un número, aunque se elimine el registro
correspondiente. Por eso el contador vive en su propia tabla (`contadores`) y
solo se incrementa, nunca se recalcula a partir de la cantidad de registros.

El incremento es un único UPDATE ... RETURNING, atómico dentro de PostgreSQL:
funciona correctamente aunque haya varios procesos o hilos a la vez.
"""

from sqlalchemy import text

from .db import get_engine


def get_last_number(tipo: str) -> int:
    with get_engine().connect() as conexion:
        valor = conexion.execute(
            text("SELECT ultimo_numero FROM contadores WHERE tipo = :tipo"), {"tipo": tipo}
        ).scalar()
    return valor or 0


def next_number(tipo: str) -> int:
    """Incrementa el contador de `tipo` y devuelve el nuevo número. Se
    confirma (commit) de inmediato, antes de guardar el registro."""
    with get_engine().begin() as conexion:
        nuevo = conexion.execute(
            text("UPDATE contadores SET ultimo_numero = ultimo_numero + 1 WHERE tipo = :tipo RETURNING ultimo_numero"),
            {"tipo": tipo},
        ).scalar()
        if nuevo is None:
            nuevo = conexion.execute(
                text("INSERT INTO contadores (tipo, ultimo_numero) VALUES (:tipo, 1) RETURNING ultimo_numero"),
                {"tipo": tipo},
            ).scalar()
    return nuevo
