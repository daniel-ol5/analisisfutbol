"""agregar tabla token_recuperacion

Revision ID: b3e8f1a6c720
Revises: 7c4d2a9e5b13
Create Date: 2026-10-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e8f1a6c720'
down_revision: Union[str, Sequence[str], None] = '7c4d2a9e5b13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('token_recuperacion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('jti', sa.String(length=64), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expira_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('usado_en', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_recuperacion_jti'), 'token_recuperacion', ['jti'], unique=True)
    op.create_index(op.f('ix_token_recuperacion_usuario_id'), 'token_recuperacion', ['usuario_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_token_recuperacion_usuario_id'), table_name='token_recuperacion')
    op.drop_index(op.f('ix_token_recuperacion_jti'), table_name='token_recuperacion')
    op.drop_table('token_recuperacion')
