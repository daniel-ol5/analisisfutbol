"""fusiona calibracion con gestion deportiva

Revision ID: 2104fa7dec50
Revises: 1aec3dc1487e, b7d41e5c9a02
Create Date: 2026-10-29 19:23:18.765276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2104fa7dec50'
down_revision: Union[str, Sequence[str], None] = ('1aec3dc1487e', 'b7d41e5c9a02')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
