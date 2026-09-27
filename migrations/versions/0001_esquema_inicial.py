"""esquema inicial

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _texto(nombre):
    return sa.Column(nombre, sa.Text(), nullable=False, server_default="")


def upgrade():
    op.create_table(
        "clientes",
        sa.Column("id", sa.String(20), primary_key=True),
        _texto("nombre"), _texto("dni_cuit"), _texto("telefono"), _texto("email"),
        _texto("direccion"), _texto("localidad"), _texto("codigo_postal"), _texto("observaciones"),
    )

    op.create_table(
        "boletos",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False, unique=True),
        sa.Column("cliente_id", sa.String(20), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        _texto("hora"), _texto("equipo"), _texto("marca"), _texto("modelo"),
        _texto("numero_serie"), _texto("especificaciones"), _texto("accesorios"),
        _texto("estado_fisico"), _texto("problema"), _texto("observaciones"),
    )
    op.create_index("ix_boletos_cliente_id", "boletos", ["cliente_id"])

    op.create_table(
        "recibos",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False, unique=True),
        sa.Column("cliente_id", sa.String(20), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("boleto_id", sa.String(20), sa.ForeignKey("boletos.id", ondelete="SET NULL")),
        sa.Column("fecha", sa.Date(), nullable=False),
        _texto("trabajo"), _texto("descripcion"),
        sa.Column("importe", sa.Numeric(12, 2)),
        _texto("forma_pago"), _texto("observaciones"),
    )
    op.create_index("ix_recibos_cliente_id", "recibos", ["cliente_id"])
    op.create_index("ix_recibos_boleto_id", "recibos", ["boleto_id"])

    op.create_table(
        "equipos",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("cliente_id", sa.String(20), sa.ForeignKey("clientes.id"), nullable=False),
        _texto("tipo"), _texto("marca"), _texto("modelo"), _texto("numero_serie"),
        sa.UniqueConstraint("cliente_id", "numero_serie"),
    )
    op.create_index("ix_equipos_cliente_id", "equipos", ["cliente_id"])

    op.create_table(
        "configuracion",
        sa.Column("id", sa.Integer(), primary_key=True),
        _texto("nombre"), _texto("cuit"), _texto("telefono"), _texto("email"),
        _texto("direccion"), _texto("localidad"), _texto("codigo_postal"),
        _texto("logo"), _texto("logo_mime"),
        sa.Column("logo_data", sa.LargeBinary()),
    )

    contadores = op.create_table(
        "contadores",
        sa.Column("tipo", sa.String(20), primary_key=True),
        sa.Column("ultimo_numero", sa.Integer(), nullable=False, server_default="0"),
    )
    op.bulk_insert(contadores, [
        {"tipo": "cliente", "ultimo_numero": 0},
        {"tipo": "boleto", "ultimo_numero": 0},
        {"tipo": "recibo", "ultimo_numero": 0},
    ])


def downgrade():
    for tabla in ("contadores", "configuracion", "equipos", "recibos", "boletos", "clientes"):
        op.drop_table(tabla)
