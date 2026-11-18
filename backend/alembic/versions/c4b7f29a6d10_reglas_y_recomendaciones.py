"""CU-49: reglas tácticas, recomendaciones y catálogo inicial."""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "c4b7f29a6d10"
down_revision = "a9d8c1e7f302"
branch_labels = None
depends_on = None


def upgrade() -> None:
    reglas = op.create_table(
        "regla_tactica",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("club.id"), nullable=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("condicion", sa.JSON(), nullable=False),
        sa.Column("plantilla_mensaje", sa.Text(), nullable=False),
        sa.Column("plantilla_justificacion", sa.Text(), nullable=False),
        sa.Column("prioridad", sa.String(10), nullable=False),
        sa.Column("cooldown_s", sa.Integer(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.CheckConstraint("cooldown_s BETWEEN 30 AND 3600", name="ck_regla_tactica_cooldown"),
    )
    op.create_index("ix_regla_tactica_club_id", "regla_tactica", ["club_id"])
    op.create_table(
        "recomendacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("partido_id", sa.Integer(), sa.ForeignKey("partido.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regla_id", sa.Integer(), sa.ForeignKey("regla_tactica.id"), nullable=False),
        sa.Column("t", sa.Float(), nullable=False),
        sa.Column("minuto", sa.Integer(), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=False),
        sa.Column("prioridad", sa.String(10), nullable=False),
        sa.Column("datos_soporte", sa.JSON(), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("util", sa.Boolean(), nullable=True),
        sa.Column("comentario", sa.String(400), nullable=True),
        sa.Column("vista_en", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("partido_id", "regla_id", "t", name="ux_recomendacion_regla_instante"),
    )
    catalogo = json.loads(Path(__file__).with_name("c4b7f29a6d10_reglas_iniciales.json").read_text(encoding="utf-8"))
    filas = [dict(club_id=None, activa=True, **regla) for regla in catalogo]
    if op.get_context().as_sql:
        for fila in filas:
            literal = op.inline_literal(json.dumps(fila["condicion"], ensure_ascii=False))
            fila["condicion"] = sa.cast(literal, sa.JSON()) if op.get_bind().dialect.name == "postgresql" else literal
            op.execute(reglas.insert().values(**fila))
    else:
        op.bulk_insert(reglas, filas)


def downgrade() -> None:
    op.drop_table("recomendacion")
    op.drop_index("ix_regla_tactica_club_id", table_name="regla_tactica")
    op.drop_table("regla_tactica")
