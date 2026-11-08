"""fusiona competiciones y modelo ml

Las dos ramas salen de 45ab6203ecca y tocan tablas distintas
(competicion y modelo_ml), así que la fusión no cambia el esquema.

Revision ID: 7d2e4a9c1f63
Revises: 8f6c2d9a4b10, c9f3a1d7e2b5
Create Date: 2026-11-08 12:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '7d2e4a9c1f63'
down_revision: Union[str, Sequence[str], None] = ('8f6c2d9a4b10', 'c9f3a1d7e2b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
