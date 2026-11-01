"""crear tabla calibracion

Revision ID: b7d41e5c9a02
Revises: 201cdd3096a4
Create Date: 2026-10-23 08:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d41e5c9a02'
down_revision: Union[str, Sequence[str], None] = '201cdd3096a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('calibracion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('club_id', sa.Integer(), nullable=False),
    # TODO: agregar la clave foranea a partido.id cuando esa tabla llegue a main.
    sa.Column('partido_id', sa.Integer(), nullable=False),
    sa.Column('largo_m', sa.Float(), nullable=False),
    sa.Column('ancho_m', sa.Float(), nullable=False),
    sa.Column('puntos_imagen', sa.JSON(), nullable=False),
    sa.Column('puntos_cancha', sa.JSON(), nullable=False),
    sa.Column('matriz_h', sa.JSON(none_as_null=True), nullable=True),
    sa.Column('error_medio_m', sa.Float(), nullable=True),
    sa.Column('error_max_m', sa.Float(), nullable=True),
    sa.Column('valida', sa.Boolean(), nullable=False),
    sa.Column('coef_distorsion', sa.JSON(none_as_null=True), nullable=True),
    sa.Column('creada_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['club.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('club_id', 'partido_id', name='uq_calibracion_club_partido')
    )
    with op.batch_alter_table('calibracion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_calibracion_club_id'), ['club_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_calibracion_partido_id'), ['partido_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('calibracion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_calibracion_partido_id'))
        batch_op.drop_index(batch_op.f('ix_calibracion_club_id'))

    op.drop_table('calibracion')
