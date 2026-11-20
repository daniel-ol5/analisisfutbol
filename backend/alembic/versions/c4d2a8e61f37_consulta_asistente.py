"""consulta_asistente: preguntas por usuario y día al asistente de uso

Guarda cuántas preguntas hizo cada usuario en el día (UTC) para aplicar
ASISTENTE_MAX_PREGUNTAS_DIA. Tabla nueva: no toca ninguna existente.

Revision ID: c4d2a8e61f37
Revises: b7e3c91d4a52
Create Date: 2026-11-19 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d2a8e61f37"
down_revision: str | Sequence[str] | None = "b7e3c91d4a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consulta_asistente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["club.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "fecha", name="uq_consulta_asistente_usuario_fecha"),
    )
    op.create_index(
        op.f("ix_consulta_asistente_club_id"), "consulta_asistente", ["club_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_consulta_asistente_club_id"), table_name="consulta_asistente")
    op.drop_table("consulta_asistente")
