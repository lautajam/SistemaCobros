"""auditoria: también clientes (editar, deshabilitar/habilitar, eliminar)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_auditoria_documento", "auditoria_documentos", type_="check")
    op.create_check_constraint("ck_auditoria_documento", "auditoria_documentos", "documento IN ('boleto', 'recibo', 'cliente')")


def downgrade():
    op.drop_constraint("ck_auditoria_documento", "auditoria_documentos", type_="check")
    op.create_check_constraint("ck_auditoria_documento", "auditoria_documentos", "documento IN ('boleto', 'recibo')")
