"""alineacion unica por partido

Revision ID: d51a7c2e9f04
Revises: b3e8f1a6c720
Create Date: 2026-10-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd51a7c2e9f04'
down_revision: Union[str, Sequence[str], None] = 'b3e8f1a6c720'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_alineacion_partido_id'), table_name='alineacion')
    op.create_index(op.f('ix_alineacion_partido_id'), 'alineacion', ['partido_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_alineacion_partido_id'), table_name='alineacion')
    op.create_index(op.f('ix_alineacion_partido_id'), 'alineacion', ['partido_id'], unique=False)
