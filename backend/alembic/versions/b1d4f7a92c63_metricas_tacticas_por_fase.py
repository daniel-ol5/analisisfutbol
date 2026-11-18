"""metricas tacticas por fase (T-102, CU-45)

Revision ID: b1d4f7a92c63
Revises: a9d8c1e7f302
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "b1d4f7a92c63"
down_revision = "a9d8c1e7f302"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("metrica_intervalo", sa.Column("suma_altura_cb_m", sa.Float(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("n_altura_cb", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("suma_amplitud_cb_m", sa.Float(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("suma_compacidad_cb_m", sa.Float(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("n_forma_cb", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("suma_altura_sb_m", sa.Float(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("n_altura_sb", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("suma_amplitud_sb_m", sa.Float(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("suma_compacidad_sb_m", sa.Float(), nullable=False, server_default="0"))
    op.add_column("metrica_intervalo", sa.Column("n_forma_sb", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("metrica_intervalo", "n_forma_sb")
    op.drop_column("metrica_intervalo", "suma_compacidad_sb_m")
    op.drop_column("metrica_intervalo", "suma_amplitud_sb_m")
    op.drop_column("metrica_intervalo", "n_altura_sb")
    op.drop_column("metrica_intervalo", "suma_altura_sb_m")
    op.drop_column("metrica_intervalo", "n_forma_cb")
    op.drop_column("metrica_intervalo", "suma_compacidad_cb_m")
    op.drop_column("metrica_intervalo", "suma_amplitud_cb_m")
    op.drop_column("metrica_intervalo", "n_altura_cb")
    op.drop_column("metrica_intervalo", "suma_altura_cb_m")
