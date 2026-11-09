"""crear tabla asignacion_track

Revision ID: a4d9e2b71c63
Revises: f1a8c3e79b24
Create Date: 2026-11-08 15:53:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d9e2b71c63"
down_revision: str | Sequence[str] | None = "f1a8c3e79b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "asignacion_track",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("jugador_id", sa.Integer(), nullable=True),
        sa.Column("equipo_detectado", sa.String(length=20), nullable=False),
        sa.Column("desde_t", sa.Float(), nullable=False),
        sa.Column("hasta_t", sa.Float(), nullable=True),
        sa.Column("confianza", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["club.id"]),
        sa.ForeignKeyConstraint(["jugador_id"], ["jugador.id"]),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("asignacion_track", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_asignacion_track_club_id"), ["club_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_asignacion_track_jugador_id"), ["jugador_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_asignacion_track_partido_id"), ["partido_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_asignacion_track_track_id"), ["track_id"], unique=False
        )
        batch_op.create_index(
            "ux_asignacion_track_partido_track_activo",
            ["partido_id", "track_id"],
            unique=True,
            postgresql_where=sa.text("hasta_t IS NULL"),
            sqlite_where=sa.text("hasta_t IS NULL"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("asignacion_track", schema=None) as batch_op:
        batch_op.drop_index(
            "ux_asignacion_track_partido_track_activo",
            postgresql_where=sa.text("hasta_t IS NULL"),
            sqlite_where=sa.text("hasta_t IS NULL"),
        )
        batch_op.drop_index(batch_op.f("ix_asignacion_track_track_id"))
        batch_op.drop_index(batch_op.f("ix_asignacion_track_partido_id"))
        batch_op.drop_index(batch_op.f("ix_asignacion_track_jugador_id"))
        batch_op.drop_index(batch_op.f("ix_asignacion_track_club_id"))

    op.drop_table("asignacion_track")
