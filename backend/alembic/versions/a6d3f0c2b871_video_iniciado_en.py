"""video: inicio del procesamiento

HU-25 (CU-27) · Criterio 2: con el momento en que el worker empezo se estima
el tiempo restante.

Revision ID: a6d3f0c2b871
Revises: e4f2a7b8c913
Create Date: 2026-11-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6d3f0c2b871'
down_revision: Union[str, Sequence[str], None] = 'e4f2a7b8c913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('video', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iniciado_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('video', schema=None) as batch_op:
        batch_op.drop_column('iniciado_en')
