"""crear tabla posicion (T-033)

Revision ID: c3f8a2d6e914
Revises: 6ece472fcc26
Create Date: 2026-11-09 22:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3f8a2d6e914"
down_revision: str | Sequence[str] | None = "6ece472fcc26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posicion",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("t", sa.Numeric(precision=8, scale=2, asdecimal=False), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("x_m", sa.Numeric(precision=6, scale=2, asdecimal=False), nullable=False),
        sa.Column("y_m", sa.Numeric(precision=6, scale=2, asdecimal=False), nullable=False),
        sa.Column("confianza", sa.Numeric(precision=4, scale=3, asdecimal=False), nullable=True),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posicion_partido_t", "posicion", ["partido_id", "t"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_posicion_partido_t", table_name="posicion")
    op.drop_table("posicion")
