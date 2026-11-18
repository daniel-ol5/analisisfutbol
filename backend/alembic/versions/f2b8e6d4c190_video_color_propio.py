"""video: columna color_propio faltante (T-061)

`app/vision/models.py::Video.color_propio` se agrego durante Sprint 3 sin su
migracion: la unica que toco esta tabla (e4f2a7b8c913) solo agrega
`color_rival` y `tomado_en`. Las pruebas no lo detectaron porque usan
`Base.metadata.create_all` en vez de Alembic (ver tests/conftest.py).

Revision ID: f2b8e6d4c190
Revises: a7c5e3f91d28
Create Date: 2026-11-10 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b8e6d4c190"
down_revision: str | Sequence[str] | None = "a7c5e3f91d28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("video", schema=None) as batch_op:
        batch_op.add_column(sa.Column("color_propio", sa.String(length=7), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("video", schema=None) as batch_op:
        batch_op.drop_column("color_propio")
