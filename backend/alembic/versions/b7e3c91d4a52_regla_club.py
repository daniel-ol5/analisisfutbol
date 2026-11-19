"""CU-54 (T-092): activación de las reglas globales por club."""

import sqlalchemy as sa
from alembic import op

revision = "b7e3c91d4a52"
down_revision = "6d8f2a1c9b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regla_club",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("club.id"), nullable=False),
        sa.Column("regla_id", sa.Integer(),
                  sa.ForeignKey("regla_tactica.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("club_id", "regla_id", name="uq_regla_club"),
    )
    op.create_index("ix_regla_club_club_id", "regla_club", ["club_id"])


def downgrade() -> None:
    op.drop_index("ix_regla_club_club_id", table_name="regla_club")
    op.drop_table("regla_club")
