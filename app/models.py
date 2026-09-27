"""
models.py
---------
Definiciones de columnas de cada CSV y helpers de formato de IDs/números.
No hay ORM ni base de datos: estas listas son literalmente el encabezado de
cada archivo CSV.
"""

CLIENTE_FIELDS = [
    "id", "nombre", "dni_cuit", "telefono", "email",
    "direccion", "localidad", "codigo_postal", "observaciones",
]

BOLETO_FIELDS = [
    "id", "numero", "cliente_id", "fecha", "hora", "equipo", "marca",
    "modelo", "numero_serie", "especificaciones", "accesorios",
    "estado_fisico", "problema", "observaciones",
]

RECIBO_FIELDS = [
    "id", "numero", "cliente_id", "boleto_id", "fecha", "trabajo",
    "descripcion", "importe", "forma_pago", "observaciones",
]

EQUIPO_FIELDS = [
    "id", "cliente_id", "tipo", "marca", "modelo", "numero_serie",
]

CONFIG_FIELDS = [
    "nombre", "cuit", "telefono", "email", "direccion",
    "localidad", "codigo_postal", "logo",
]


def format_cliente_id(numero: int) -> str:
    return f"C{numero:05d}"


def format_boleto_numero(numero: int) -> str:
    return f"{numero:04d}"


def format_recibo_numero(numero: int) -> str:
    return f"{numero:04d}"


def format_boleto_id(numero_str: str) -> str:
    return f"B{numero_str}"


def format_recibo_id(numero_str: str) -> str:
    return f"R{numero_str}"
