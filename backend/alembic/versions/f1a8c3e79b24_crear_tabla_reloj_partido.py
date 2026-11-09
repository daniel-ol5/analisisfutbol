"""crear tabla reloj_partido

Revision ID: f1a8c3e79b24
Revises: e9c1b7f4a260
Create Date: 2026-11-07 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a8c3e79b24"
down_revision: str | Sequence[str] | None = "e9c1b7f4a260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "reloj_partido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("parte", sa.Integer(), nullable=False),
        sa.Column("en_curso", sa.Boolean(), nullable=False),
        sa.Column("inicio_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acumulado_s", sa.Float(), nullable=False),
        sa.Column("descuento_1_min", sa.Integer(), nullable=False),
        sa.Column("descuento_2_min", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["club.id"]),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partido_id", name="uq_reloj_partido_partido"),
    )
    with op.batch_alter_table("reloj_partido", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_reloj_partido_club_id"), ["club_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_reloj_partido_partido_id"), ["partido_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("reloj_partido", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reloj_partido_partido_id"))
        batch_op.drop_index(batch_op.f("ix_reloj_partido_club_id"))

    op.drop_table("reloj_partido")
