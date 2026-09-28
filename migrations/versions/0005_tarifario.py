"""tarifario: categorias_trabajo y trabajos

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "categorias_trabajo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(60), nullable=False),
    )
    op.create_index("uq_categorias_trabajo_nombre_lower", "categorias_trabajo", [sa.text("lower(nombre)")], unique=True)

    op.create_table(
        "trabajos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False, server_default=""),
        sa.Column("categoria", sa.Text(), nullable=False, server_default=""),
        sa.Column("descripcion", sa.Text(), nullable=False, server_default=""),
        sa.Column("precio", sa.Numeric(12, 2)),
        sa.Column("precio_desde", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("complejidad", sa.String(20), nullable=False, server_default="basico"),
        sa.CheckConstraint("complejidad IN ('basico', 'complejo', 'avanzado')", name="ck_trabajos_complejidad"),
    )
    op.create_index("ix_trabajos_categoria", "trabajos", ["categoria"])


def downgrade():
    op.drop_table("trabajos")
    op.drop_index("uq_categorias_trabajo_nombre_lower", table_name="categorias_trabajo")
    op.drop_table("categorias_trabajo")
