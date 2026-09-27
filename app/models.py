"""
models.py
---------
Tablas de PostgreSQL (SQLAlchemy) y helpers de formato de IDs/números.

Cada modelo sabe convertirse a un dict de strings (`to_dict`), que es lo que
consumen las plantillas de la interfaz y las de los PDF.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Columnas de cada documento, usadas para armar los documentos en blanco.
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


class Base(DeclarativeBase):
    pass


class Serializable:
    OCULTAS = ()

    def to_dict(self) -> dict:
        datos = {}
        for columna in self.__table__.columns:
            if columna.name in self.OCULTAS:
                continue
            valor = getattr(self, columna.name)
            if valor is None:
                valor = ""
            elif isinstance(valor, dt.date):
                valor = valor.isoformat()
            elif isinstance(valor, Decimal):
                valor = format(valor, "f")
            datos[columna.name] = valor
        return datos


def _texto():
    return mapped_column(Text, nullable=False, default="", server_default="")


class Cliente(Serializable, Base):
    __tablename__ = "clientes"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = _texto()
    dni_cuit: Mapped[str] = _texto()
    telefono: Mapped[str] = _texto()
    email: Mapped[str] = _texto()
    direccion: Mapped[str] = _texto()
    localidad: Mapped[str] = _texto()
    codigo_postal: Mapped[str] = _texto()
    observaciones: Mapped[str] = _texto()


class Boleto(Serializable, Base):
    __tablename__ = "boletos"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    fecha: Mapped[dt.date] = mapped_column(Date, nullable=False)
    hora: Mapped[str] = _texto()
    equipo: Mapped[str] = _texto()
    marca: Mapped[str] = _texto()
    modelo: Mapped[str] = _texto()
    numero_serie: Mapped[str] = _texto()
    especificaciones: Mapped[str] = _texto()
    accesorios: Mapped[str] = _texto()
    estado_fisico: Mapped[str] = _texto()
    problema: Mapped[str] = _texto()
    observaciones: Mapped[str] = _texto()


class Recibo(Serializable, Base):
    __tablename__ = "recibos"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    boleto_id: Mapped[str | None] = mapped_column(ForeignKey("boletos.id", ondelete="SET NULL"), index=True)
    fecha: Mapped[dt.date] = mapped_column(Date, nullable=False)
    trabajo: Mapped[str] = _texto()
    descripcion: Mapped[str] = _texto()
    importe: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    forma_pago: Mapped[str] = _texto()
    observaciones: Mapped[str] = _texto()


class Equipo(Serializable, Base):
    """Auxiliar: se completa solo si el boleto trae N.º de serie, para poder
    consultar en el futuro el historial de un mismo equipo."""

    __tablename__ = "equipos"
    __table_args__ = (UniqueConstraint("cliente_id", "numero_serie"),)

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    tipo: Mapped[str] = _texto()
    marca: Mapped[str] = _texto()
    modelo: Mapped[str] = _texto()
    numero_serie: Mapped[str] = _texto()


class Configuracion(Serializable, Base):
    """Una sola fila (id = 1) con los datos del service. El logo se guarda en
    la propia base, así viaja dentro de los backups."""

    __tablename__ = "configuracion"
    OCULTAS = ("logo_data",)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = _texto()
    cuit: Mapped[str] = _texto()
    telefono: Mapped[str] = _texto()
    email: Mapped[str] = _texto()
    direccion: Mapped[str] = _texto()
    localidad: Mapped[str] = _texto()
    codigo_postal: Mapped[str] = _texto()
    logo: Mapped[str] = _texto()
    logo_mime: Mapped[str] = _texto()
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary)


class Contador(Base):
    """Último número emitido por tipo (cliente / boleto / recibo). Solo se
    incrementa: un número nunca se reutiliza, aunque se borre el registro."""

    __tablename__ = "contadores"

    tipo: Mapped[str] = mapped_column(String(20), primary_key=True)
    ultimo_numero: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


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
