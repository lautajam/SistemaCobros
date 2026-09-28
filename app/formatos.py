"""Formatos de presentación compartidos."""

from decimal import Decimal, InvalidOperation


def pesos(valor):
    """45000.5 -> '45.000,50' (formato argentino). Vacío -> '0,00'."""
    try:
        numero = Decimal(str(valor).strip() or "0")
    except InvalidOperation:
        return valor
    texto = f"{numero:,.2f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")
