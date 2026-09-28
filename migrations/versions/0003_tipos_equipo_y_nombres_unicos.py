"""tipos de equipo (lista administrable), equipo en los recibos y nombres de usuario unicos

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TIPOS_INICIALES = ["PC", "Notebook", "All in one", "Impresora", "Monitor", "Celular", "Tablet", "Consola", "Otro"]


def upgrade():
    # Nombres de usuario únicos sin distinguir mayúsculas. Si ya había repetidos,
    # se les agrega su número para poder crear el índice sin perder a nadie.
    op.execute(
        "UPDATE usuarios u SET nombre = u.nombre || ' (' || u.id || ')' "
        "WHERE EXISTS (SELECT 1 FROM usuarios o WHERE lower(trim(o.nombre)) = lower(trim(u.nombre)) AND o.id < u.id)"
    )
    op.execute("CREATE UNIQUE INDEX uq_usuarios_nombre_lower ON usuarios (lower(nombre))")

    tipos = op.create_table(
        "tipos_equipo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(60), nullable=False),
    )
    op.execute("CREATE UNIQUE INDEX uq_tipos_equipo_nombre_lower ON tipos_equipo (lower(nombre))")
    op.bulk_insert(tipos, [{"nombre": nombre} for nombre in TIPOS_INICIALES])
    # Los tipos que ya se usaron en boletos existentes se conservan en la lista.
    op.execute(
        "INSERT INTO tipos_equipo (nombre) SELECT DISTINCT trim(equipo) FROM boletos "
        "WHERE trim(equipo) <> '' AND length(trim(equipo)) <= 60 ON CONFLICT DO NOTHING"
    )

    op.add_column("recibos", sa.Column("equipo", sa.Text(), nullable=False, server_default=""))


def downgrade():
    op.drop_column("recibos", "equipo")
    op.drop_table("tipos_equipo")
    op.execute("DROP INDEX IF EXISTS uq_usuarios_nombre_lower")
