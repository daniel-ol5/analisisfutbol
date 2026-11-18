"""Modo de calibración y referencia de fuente/cuadro."""
import sqlalchemy as sa
from alembic import op

revision = "a9d8c1e7f302"
down_revision = "a7c5e3f91d28"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("calibracion") as tabla:
        tabla.add_column(sa.Column("modo", sa.String(16), nullable=False, server_default="MANUAL"))
        tabla.add_column(sa.Column("referencia", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    with op.batch_alter_table("calibracion") as tabla:
        tabla.drop_column("referencia")
        tabla.drop_column("modo")
