"""competicion unica por club nombre y temporada

Revision ID: 8f6c2d9a4b10
Revises: 45ab6203ecca
Create Date: 2026-11-05

"""

from collections.abc import Sequence

from alembic import op

revision: str = "8f6c2d9a4b10"
down_revision: str | Sequence[str] | None = "45ab6203ecca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("competicion") as batch_op:
        batch_op.create_unique_constraint(
            "uq_competicion_club_nombre_temporada",
            ["club_id", "nombre", "temporada"],
        )


def downgrade() -> None:
    with op.batch_alter_table("competicion") as batch_op:
        batch_op.drop_constraint(
            "uq_competicion_club_nombre_temporada",
            type_="unique",
        )
