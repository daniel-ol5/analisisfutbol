"""modelo_ml: registro de activacion

T-064 (CU-29): quien activo cada version, cuando, y por que se forzo si tenia
metricas peores que la vigente.

Revision ID: d8b4e6a1c235
Revises: a6d3f0c2b871
Create Date: 2026-11-09 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b4e6a1c235'
down_revision: Union[str, Sequence[str], None] = 'a6d3f0c2b871'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('modelo_ml', schema=None) as batch_op:
        batch_op.add_column(sa.Column('activado_en', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('activado_por_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('motivo_activacion', sa.String(length=300), nullable=True))
        batch_op.create_foreign_key(
            'fk_modelo_ml_activado_por_id_usuario', 'usuario', ['activado_por_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('modelo_ml', schema=None) as batch_op:
        batch_op.drop_constraint('fk_modelo_ml_activado_por_id_usuario', type_='foreignkey')
        batch_op.drop_column('motivo_activacion')
        batch_op.drop_column('activado_por_id')
        batch_op.drop_column('activado_en')
