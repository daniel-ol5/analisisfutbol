"""crear tabla evento_derivado (T-103, CU-47) y unir las cabezas de migración

Hasta ahora había dos cabezas sin unir: `b1d4f7a92c63` (métricas tácticas por fase,
T-102) y `f2b8e6d4c190` (columna `video.color_propio`). Con dos cabezas,
`alembic upgrade head` se niega a correr. Esta revisión las une y, de paso, crea la
tabla `evento_derivado` de docs/diagramas/modelo-datos.puml.

Se agregan `track_origen_id` y `track_destino_id`, que el diagrama no tiene: sirven para
resolver el jugador vigente aunque el track se reasigne después (ver el modelo).

Revision ID: d4a1b8c6e703
Revises: b1d4f7a92c63, f2b8e6d4c190
Create Date: 2026-11-18 00:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4a1b8c6e703"
down_revision: str | Sequence[str] | None = ("b1d4f7a92c63", "f2b8e6d4c190")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evento_derivado",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("jugador_origen_id", sa.Integer(), nullable=True),
        sa.Column("jugador_destino_id", sa.Integer(), nullable=True),
        sa.Column("track_origen_id", sa.Integer(), nullable=True),
        sa.Column("track_destino_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=15), nullable=False),
        sa.Column("t", sa.Numeric(precision=8, scale=2, asdecimal=False), nullable=False),
        sa.Column("minuto", sa.Integer(), nullable=True),
        sa.Column("equipo", sa.String(length=15), nullable=True),
        sa.Column("x_o", sa.Numeric(precision=6, scale=2, asdecimal=False), nullable=True),
        sa.Column("y_o", sa.Numeric(precision=6, scale=2, asdecimal=False), nullable=True),
        sa.Column("x_d", sa.Numeric(precision=6, scale=2, asdecimal=False), nullable=True),
        sa.Column("y_d", sa.Numeric(precision=6, scale=2, asdecimal=False), nullable=True),
        sa.Column("resultado", sa.String(length=10), nullable=True),
        sa.Column("confianza", sa.Numeric(precision=4, scale=3, asdecimal=False), nullable=True),
        sa.Column("origen", sa.String(length=10), nullable=False, server_default="CAMARA"),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["jugador_origen_id"], ["jugador.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["jugador_destino_id"], ["jugador.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evento_derivado_partido_t", "evento_derivado", ["partido_id", "t"],
                    unique=False)


def downgrade() -> None:
    op.drop_index("ix_evento_derivado_partido_t", table_name="evento_derivado")
    op.drop_table("evento_derivado")
