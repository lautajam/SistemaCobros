"""auditoria de boletos y recibos, y tipos de equipo desactivables

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Nombre del PDF emitido: el documento se entrega tal cual salió, aunque después cambie el cliente.
    op.add_column("boletos", sa.Column("pdf_archivo", sa.Text(), nullable=False, server_default=""))
    op.add_column("recibos", sa.Column("pdf_archivo", sa.Text(), nullable=False, server_default=""))
    op.add_column("tipos_equipo", sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.create_table(
        "auditoria_documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento", sa.String(10), nullable=False),
        sa.Column("documento_id", sa.String(20), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False, server_default=""),
        sa.Column("accion", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("usuario_texto", sa.Text(), nullable=False, server_default=""),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cambios", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.CheckConstraint("documento IN ('boleto', 'recibo')", name="ck_auditoria_documento"),
        sa.CheckConstraint("accion IN ('editado', 'eliminado')", name="ck_auditoria_accion"),
    )
    op.create_index("ix_auditoria_documento", "auditoria_documentos", ["documento", "documento_id"])
    op.create_index("ix_auditoria_momento", "auditoria_documentos", ["momento"])


def downgrade():
    op.drop_table("auditoria_documentos")
    op.drop_column("tipos_equipo", "activo")
    op.drop_column("recibos", "pdf_archivo")
    op.drop_column("boletos", "pdf_archivo")
