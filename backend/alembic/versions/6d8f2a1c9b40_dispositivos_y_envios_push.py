"""CU-53: dispositivos FCM e historial idempotente de envios push."""

import sqlalchemy as sa
from alembic import op

revision = "6d8f2a1c9b40"
down_revision = "3bde7296b8ea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispositivo_push",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("club.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("instalacion_id", sa.String(128), nullable=False, unique=True),
        sa.Column("token", sa.String(4096), nullable=False),
        sa.Column("plataforma", sa.String(12), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("ultimo_error", sa.String(400), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dispositivo_push_club_id", "dispositivo_push", ["club_id"])
    op.create_index("ix_dispositivo_push_usuario_id", "dispositivo_push", ["usuario_id"])
    op.create_index(
        "ux_dispositivo_push_token_activo",
        "dispositivo_push",
        ["token"],
        unique=True,
        postgresql_where=sa.text("activo"),
    )
    op.create_table(
        "envio_push",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recomendacion_id",
            sa.Integer(),
            sa.ForeignKey("recomendacion.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dispositivo_id",
            sa.Integer(),
            sa.ForeignKey("dispositivo_push.id"),
            nullable=False,
        ),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("proveedor_id", sa.String(300), nullable=True),
        sa.Column("error", sa.String(400), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviado_en", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "recomendacion_id",
            "dispositivo_id",
            name="uq_envio_push_recomendacion_dispositivo",
        ),
    )
    op.create_index("ix_envio_push_recomendacion_id", "envio_push", ["recomendacion_id"])
    op.create_index("ix_envio_push_dispositivo_id", "envio_push", ["dispositivo_id"])


def downgrade() -> None:
    op.drop_table("envio_push")
    op.drop_index("ux_dispositivo_push_token_activo", table_name="dispositivo_push")
    op.drop_index("ix_dispositivo_push_usuario_id", table_name="dispositivo_push")
    op.drop_index("ix_dispositivo_push_club_id", table_name="dispositivo_push")
    op.drop_table("dispositivo_push")

