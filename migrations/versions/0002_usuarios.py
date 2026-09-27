"""usuarios, roles, intentos de login y ajustes

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario", sa.String(50), nullable=False, unique=True),
        sa.Column("nombre", sa.Text(), nullable=False, server_default=""),
        sa.Column("rol", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("debe_cambiar_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("creado", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ultimo_ingreso", sa.DateTime(timezone=True)),
        sa.CheckConstraint("rol IN ('admin', 'tecnico')", name="ck_usuarios_rol"),
    )

    op.create_table(
        "sesiones",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creado", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ultimo_uso", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sesiones_usuario_id", "sesiones", ["usuario_id"])

    op.create_table(
        "intentos_login",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip", sa.String(64), nullable=False, server_default=""),
        sa.Column("usuario", sa.String(50), nullable=False, server_default=""),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_intentos_login_usuario_momento", "intentos_login", ["usuario", "momento"])
    op.create_index("ix_intentos_login_ip_momento", "intentos_login", ["ip", "momento"])

    op.create_table(
        "ajustes",
        sa.Column("clave", sa.String(50), primary_key=True),
        sa.Column("valor", sa.Text(), nullable=False),
    )

    for tabla in ("boletos", "recibos"):
        op.add_column(tabla, sa.Column("creado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")))
        op.create_index(f"ix_{tabla}_creado_por_id", tabla, ["creado_por_id"])


def downgrade():
    for tabla in ("recibos", "boletos"):
        op.drop_index(f"ix_{tabla}_creado_por_id", table_name=tabla)
        op.drop_column(tabla, "creado_por_id")
    op.drop_table("ajustes")
    op.drop_table("intentos_login")
    op.drop_table("sesiones")
    op.drop_table("usuarios")
