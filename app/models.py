"""
models.py
---------
Tablas de PostgreSQL (SQLAlchemy) y helpers de formato de IDs/números.

Cada modelo sabe convertirse a un dict de strings (`to_dict`), que es lo que
consumen las plantillas de la interfaz y las de los PDF.
"""

import datetime as dt
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text,
    Index, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    "id", "numero", "cliente_id", "boleto_id", "fecha", "equipo", "trabajo",
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
    # Deshabilitado: no aparece en la búsqueda ni se le pueden generar documentos nuevos,
    # pero conserva su historial (boletos, recibos) intacto y se puede volver a habilitar.
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Boleto(Serializable, Base):
    __tablename__ = "boletos"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
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
    pdf_archivo: Mapped[str] = _texto()


class Recibo(Serializable, Base):
    __tablename__ = "recibos"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    boleto_id: Mapped[str | None] = mapped_column(ForeignKey("boletos.id", ondelete="SET NULL"), index=True)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    fecha: Mapped[dt.date] = mapped_column(Date, nullable=False)
    equipo: Mapped[str] = _texto()
    trabajo: Mapped[str] = _texto()
    descripcion: Mapped[str] = _texto()
    importe: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    forma_pago: Mapped[str] = _texto()
    observaciones: Mapped[str] = _texto()
    pdf_archivo: Mapped[str] = _texto()


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


class Usuario(UserMixin, Base):
    """Usuario del sistema. La contraseña se guarda solo como hash."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'tecnico')", name="ck_usuarios_rol"),
        Index("uq_usuarios_nombre_lower", text("lower(nombre)"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nombre: Mapped[str] = _texto()
    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    creado: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ultimo_ingreso: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_active(self):
        return self.activo

    @property
    def es_admin(self):
        return self.rol == "admin"

    @property
    def nombre_visible(self):
        return self.nombre or self.usuario


class TipoEquipo(Base):
    """Lista de tipos de equipo (PC, Notebook...) que administra el admin y de la que
    se elige en boletos y recibos. Solo tiene nombre."""

    __tablename__ = "tipos_equipo"
    __table_args__ = (Index("uq_tipos_equipo_nombre_lower", text("lower(nombre)"), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    # Deshabilitado: ya no aparece en el desplegable, pero los documentos emitidos lo conservan.
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class AuditoriaDocumento(Base):
    """Registro de lo que un administrador hizo sobre un boleto o recibo ya emitido
    (editarlo o eliminarlo). No tiene clave foránea al documento: la constancia sobrevive
    aunque se lo elimine. No se imprime en el PDF."""

    __tablename__ = "auditoria_documentos"
    __table_args__ = (
        CheckConstraint("documento IN ('boleto', 'recibo', 'cliente')", name="ck_auditoria_documento"),
        CheckConstraint("accion IN ('editado', 'eliminado')", name="ck_auditoria_accion"),
        Index("ix_auditoria_documento", "documento", "documento_id"),
        Index("ix_auditoria_momento", "momento"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento: Mapped[str] = mapped_column(String(10), nullable=False)
    documento_id: Mapped[str] = mapped_column(String(20), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False, default="", server_default="")
    accion: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    usuario_texto: Mapped[str] = _texto()
    momento: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    cambios: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))


class CategoriaTrabajo(Base):
    """Lista de categorías del tarifario (Reparación, Mantenimiento, Instalación...) que
    administra el admin. Solo tiene nombre. Un trabajo guarda la categoría como texto
    propio: renombrar una categoría actualiza los trabajos que la usan (no son documentos
    emitidos, siempre muestran el precio y los datos vigentes); eliminarla no borra los
    trabajos, que conservan el nombre que tenían."""

    __tablename__ = "categorias_trabajo"
    __table_args__ = (Index("uq_categorias_trabajo_nombre_lower", text("lower(nombre)"), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)


COMPLEJIDADES = {"basico": "Básico", "complejo": "Complejo", "avanzado": "Avanzado"}


class Trabajo(Serializable, Base):
    """Un ítem del tarifario: un trabajo que ofrece el service, con su precio.
    No es un documento emitido (no lo referencia ningún boleto ni recibo), así que
    editarlo o eliminarlo es libre, sin auditoría ni inmutabilidad."""

    __tablename__ = "trabajos"
    __table_args__ = (CheckConstraint("complejidad IN ('basico', 'complejo', 'avanzado')", name="ck_trabajos_complejidad"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = _texto()
    categoria: Mapped[str] = _texto()
    descripcion: Mapped[str] = _texto()
    precio: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    precio_desde: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    complejidad: Mapped[str] = mapped_column(String(20), nullable=False, default="basico", server_default="basico")


class SesionActiva(Base):
    """Sesión iniciada. La cookie solo guarda el token; si la fila se borra
    (cerrar sesión, cambiar la clave, desactivar al usuario) la cookie deja
    de valer aunque alguien tenga una copia."""

    __tablename__ = "sesiones"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    creado: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ultimo_uso: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class IntentoLogin(Base):
    """Intentos de ingreso fallidos (para bloquear por usuario y por IP)."""

    __tablename__ = "intentos_login"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    usuario: Mapped[str] = mapped_column(String(50), nullable=False, default="", server_default="")
    momento: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Ajuste(Base):
    """Pares clave/valor internos (por ejemplo, la clave secreta de sesiones)."""

    __tablename__ = "ajustes"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)


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
