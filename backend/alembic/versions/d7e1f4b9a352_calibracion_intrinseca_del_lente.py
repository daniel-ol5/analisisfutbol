"""calibracion: matriz_camara y tamano_imagen (T-036)

Revision ID: d7e1f4b9a352
Revises: c3f8a2d6e914
Create Date: 2026-11-09 23:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e1f4b9a352"
down_revision: str | Sequence[str] | None = "c3f8a2d6e914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch: SQLite no altera tablas en el lugar; en PostgreSQL es un ALTER normal.
    with op.batch_alter_table("calibracion") as tabla:
        tabla.add_column(sa.Column("matriz_camara", sa.JSON(none_as_null=True), nullable=True))
        tabla.add_column(sa.Column("tamano_imagen", sa.JSON(none_as_null=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("calibracion") as tabla:
        tabla.drop_column("tamano_imagen")
        tabla.drop_column("matriz_camara")
