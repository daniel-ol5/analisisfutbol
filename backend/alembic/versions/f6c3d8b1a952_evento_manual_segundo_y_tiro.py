"""evento_manual: segundo exacto y tipo TIRO  —  T-103 (CU-47)

Revision ID: f6c3d8b1a952
Revises: e5b2c9a4d871
Create Date: 2026-11-18

- `segundo`: segundo exacto del partido, para que el plano 2D salte a la jugada y no
  solo al inicio del minuto. Nulo en los eventos anteriores y en los de minuto manual.
- `TIRO` pasa a ser un tipo permitido (la cámara todavía no detecta tiros).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6c3d8b1a952"
down_revision: str | Sequence[str] | None = "e5b2c9a4d871"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CK = "ck_evento_manual_tipo"


def upgrade() -> None:
    op.add_column("evento_manual", sa.Column("segundo", sa.Integer(), nullable=True))
    op.drop_constraint(CK, "evento_manual", type_="check")
    op.create_check_constraint(
        CK, "evento_manual", "tipo IN ('GOL', 'AMARILLA', 'ROJA', 'SUSTITUCION', 'TIRO')")


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM evento_manual WHERE tipo = 'TIRO'"))
    op.drop_constraint(CK, "evento_manual", type_="check")
    op.create_check_constraint(
        CK, "evento_manual", "tipo IN ('GOL', 'AMARILLA', 'ROJA', 'SUSTITUCION')")
    op.drop_column("evento_manual", "segundo")
