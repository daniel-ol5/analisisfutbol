"""métricas por intervalo y posicion.es_balon (T-074, T-075, T-076)

Revision ID: a7c5e3f91d28
Revises: d7e1f4b9a352
Create Date: 2026-11-09 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c5e3f91d28"
down_revision: str | Sequence[str] | None = "d7e1f4b9a352"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # T-074: el balón deja de ser indistinguible de un jugador en `posicion`.
    with op.batch_alter_table("posicion") as tabla:
        tabla.add_column(
            sa.Column("es_balon", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "metrica_intervalo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("intervalo", sa.Integer(), nullable=False),
        sa.Column("equipo", sa.String(length=15), nullable=False),
        sa.Column("minuto_desde", sa.Integer(), nullable=False),
        sa.Column("minuto_hasta", sa.Integer(), nullable=False),
        sa.Column("t_desde", sa.Float(), nullable=False),
        sa.Column("t_hasta", sa.Float(), nullable=False),
        sa.Column("parcial", sa.Boolean(), nullable=False),
        sa.Column("posesion_s", sa.Float(), nullable=False),
        sa.Column("disputa_s", sa.Float(), nullable=False),
        sa.Column("pases_intentados", sa.Integer(), nullable=False),
        sa.Column("pases_completados", sa.Integer(), nullable=False),
        sa.Column("distancia_m", sa.Float(), nullable=False),
        sa.Column("suma_altura_m", sa.Float(), nullable=False),
        sa.Column("n_altura", sa.Integer(), nullable=False),
        sa.Column("suma_amplitud_m", sa.Float(), nullable=False),
        sa.Column("suma_compacidad_m", sa.Float(), nullable=False),
        sa.Column("n_forma", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partido_id", "intervalo", "equipo",
                            name="ux_metrica_intervalo_partido_intervalo_equipo"),
    )
    op.create_index("ix_metrica_intervalo_partido_id", "metrica_intervalo", ["partido_id"])

    op.create_table(
        "metrica_track_intervalo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("intervalo", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("equipo", sa.String(length=20), nullable=False),
        sa.Column("t_desde", sa.Float(), nullable=False),
        sa.Column("t_hasta", sa.Float(), nullable=False),
        sa.Column("tiempo_s", sa.Float(), nullable=False),
        sa.Column("distancia_m", sa.Float(), nullable=False),
        sa.Column("velocidad_max_ms", sa.Float(), nullable=False),
        sa.Column("sprints", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partido_id", "intervalo", "track_id",
                            name="ux_metrica_track_intervalo_partido_intervalo_track"),
    )
    op.create_index("ix_metrica_track_intervalo_partido_id", "metrica_track_intervalo",
                    ["partido_id"])


def downgrade() -> None:
    op.drop_index("ix_metrica_track_intervalo_partido_id", table_name="metrica_track_intervalo")
    op.drop_table("metrica_track_intervalo")
    op.drop_index("ix_metrica_intervalo_partido_id", table_name="metrica_intervalo")
    op.drop_table("metrica_intervalo")
    with op.batch_alter_table("posicion") as tabla:
        tabla.drop_column("es_balon")
