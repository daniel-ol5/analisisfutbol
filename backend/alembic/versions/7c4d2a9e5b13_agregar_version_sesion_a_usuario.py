"""agregar version_sesion a usuario

Revision ID: 7c4d2a9e5b13
Revises: 1aec3dc1487e
Create Date: 2026-10-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4d2a9e5b13'
down_revision: Union[str, Sequence[str], None] = '1aec3dc1487e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'usuario',
        sa.Column('version_sesion', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usuario', 'version_sesion')
