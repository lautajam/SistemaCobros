"""clientes: deshabilitar sin eliminar

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clientes", sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade():
    op.drop_column("clientes", "activo")
