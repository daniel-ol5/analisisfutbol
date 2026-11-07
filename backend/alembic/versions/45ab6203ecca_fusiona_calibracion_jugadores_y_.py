"""fusiona calibracion jugadores y alineacion

Revision ID: 45ab6203ecca
Revises: 2104fa7dec50, d51a7c2e9f04, e2cb5e18af48
Create Date: 2026-11-02 01:22:10.523311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45ab6203ecca'
down_revision: Union[str, Sequence[str], None] = ('2104fa7dec50', 'd51a7c2e9f04', 'e2cb5e18af48')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
