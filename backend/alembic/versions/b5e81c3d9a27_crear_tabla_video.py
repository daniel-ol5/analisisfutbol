"""crear tabla video

T-060 (CU-28): video grabado del partido, cargado por partes.

Revision ID: b5e81c3d9a27
Revises: 7d2e4a9c1f63
Create Date: 2026-11-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e81c3d9a27'
down_revision: Union[str, Sequence[str], None] = '7d2e4a9c1f63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('video',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('club_id', sa.Integer(), nullable=False),
    sa.Column('partido_id', sa.Integer(), nullable=False),
    sa.Column('modelo_id', sa.Integer(), nullable=True),
    sa.Column('archivo_url', sa.String(length=400), nullable=False),
    sa.Column('nombre', sa.String(length=200), nullable=False),
    sa.Column('tipo', sa.String(length=80), nullable=False),
    sa.Column('tamano_bytes', sa.BigInteger(), nullable=False),
    sa.Column('bytes_recibidos', sa.BigInteger(), nullable=False),
    sa.Column('duracion_s', sa.Integer(), nullable=True),
    sa.Column('fps', sa.Integer(), nullable=True),
    sa.Column('resolucion', sa.String(length=20), nullable=True),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('progreso_pct', sa.Integer(), nullable=False),
    sa.Column('mensaje_error', sa.String(length=400), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('procesado_en', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['club_id'], ['club.id'], ),
    sa.ForeignKeyConstraint(['partido_id'], ['partido.id'], ),
    sa.ForeignKeyConstraint(['modelo_id'], ['modelo_ml.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('video', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_video_club_id'), ['club_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_video_partido_id'), ['partido_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_video_estado'), ['estado'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('video', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_video_estado'))
        batch_op.drop_index(batch_op.f('ix_video_partido_id'))
        batch_op.drop_index(batch_op.f('ix_video_club_id'))

    op.drop_table('video')
