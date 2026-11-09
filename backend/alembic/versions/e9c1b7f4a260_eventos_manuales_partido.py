"""eventos manuales del partido

Revision ID: e9c1b7f4a260
Revises: d8b4e6a1c235
Create Date: 2026-11-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e9c1b7f4a260"
down_revision: str | Sequence[str] | None = "d8b4e6a1c235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evento_manual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("equipo", sa.String(length=15), nullable=False),
        sa.Column("jugador_id", sa.Integer(), nullable=True),
        sa.Column("jugador_entra_id", sa.Integer(), nullable=True),
        sa.Column("minuto", sa.Integer(), nullable=False),
        sa.Column("origen", sa.String(length=15), nullable=False),
        sa.Column("convertida_en_roja", sa.Boolean(), nullable=False),
        sa.Column("capturado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_por_id", sa.Integer(), nullable=False),
        sa.Column("anulado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anulado_por_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "equipo IN ('LOCAL', 'VISITANTE')", name="ck_evento_manual_equipo"
        ),
        sa.CheckConstraint("origen = 'MANUAL'", name="ck_evento_manual_origen"),
        sa.CheckConstraint(
            "tipo IN ('GOL', 'AMARILLA', 'ROJA', 'SUSTITUCION')",
            name="ck_evento_manual_tipo",
        ),
        sa.ForeignKeyConstraint(["anulado_por_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["club_id"], ["club.id"]),
        sa.ForeignKeyConstraint(["creado_por_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["jugador_entra_id"], ["jugador.id"]),
        sa.ForeignKeyConstraint(["jugador_id"], ["jugador.id"]),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id", "uuid", name="uq_evento_manual_club_uuid"),
    )
    op.create_index("ix_evento_manual_club_id", "evento_manual", ["club_id"])
    op.create_index("ix_evento_manual_creado_por_id", "evento_manual", ["creado_por_id"])
    op.create_index("ix_evento_manual_jugador_entra_id", "evento_manual", ["jugador_entra_id"])
    op.create_index("ix_evento_manual_jugador_id", "evento_manual", ["jugador_id"])
    op.create_index(
        "ix_evento_manual_partido_creado", "evento_manual", ["partido_id", "creado_en"]
    )
    op.create_index("ix_evento_manual_partido_id", "evento_manual", ["partido_id"])


def downgrade() -> None:
    op.drop_index("ix_evento_manual_partido_id", table_name="evento_manual")
    op.drop_index("ix_evento_manual_partido_creado", table_name="evento_manual")
    op.drop_index("ix_evento_manual_jugador_id", table_name="evento_manual")
    op.drop_index("ix_evento_manual_jugador_entra_id", table_name="evento_manual")
    op.drop_index("ix_evento_manual_creado_por_id", table_name="evento_manual")
    op.drop_index("ix_evento_manual_club_id", table_name="evento_manual")
    op.drop_table("evento_manual")
