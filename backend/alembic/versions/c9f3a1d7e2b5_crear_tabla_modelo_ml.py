"""crear tabla modelo_ml

Revision ID: c9f3a1d7e2b5
Revises: 45ab6203ecca
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f3a1d7e2b5'
down_revision: Union[str, Sequence[str], None] = '45ab6203ecca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('modelo_ml',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('club_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=80), nullable=False),
    sa.Column('version', sa.String(length=20), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('archivo_url', sa.String(length=400), nullable=False),
    sa.Column('map50_jugador', sa.Float(), nullable=True),
    sa.Column('map50_balon', sa.Float(), nullable=True),
    sa.Column('idf1', sa.Float(), nullable=True),
    sa.Column('notas', sa.String(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('entrenado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['club.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('club_id', 'nombre', 'version', name='uq_modelo_club_nombre_version')
    )
    with op.batch_alter_table('modelo_ml', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_modelo_ml_club_id'), ['club_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_modelo_ml_activo'), ['activo'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('modelo_ml', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_modelo_ml_activo'))
        batch_op.drop_index(batch_op.f('ix_modelo_ml_club_id'))

    op.drop_table('modelo_ml')
