"""video: procesamiento diferido

T-061 (CU-27): color del rival indicado al lanzar el proceso y momento en que
un worker tomo el trabajo.

Revision ID: e4f2a7b8c913
Revises: b5e81c3d9a27
Create Date: 2026-11-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f2a7b8c913'
down_revision: Union[str, Sequence[str], None] = 'b5e81c3d9a27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('video', schema=None) as batch_op:
        batch_op.add_column(sa.Column('color_rival', sa.String(length=7), nullable=True))
        batch_op.add_column(sa.Column('tomado_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('video', schema=None) as batch_op:
        batch_op.drop_column('tomado_en')
        batch_op.drop_column('color_rival')
