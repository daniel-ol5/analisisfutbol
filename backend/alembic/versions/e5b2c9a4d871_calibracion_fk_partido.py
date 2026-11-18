"""calibracion.partido_id con clave foránea a partido  —  T-105

Revision ID: e5b2c9a4d871
Revises: d4a1b8c6e703
Create Date: 2026-11-18

Antes `partido_id` era un entero suelto (la tabla `partido` todavía no estaba en main) y
se podía guardar una calibración para un partido que no existe. Se borran las huérfanas,
si las hay, y se agrega la FK; al borrar un partido se borra su calibración.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b2c9a4d871"
down_revision: str | Sequence[str] | None = "d4a1b8c6e703"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK = "fk_calibracion_partido_id_partido"


def upgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM calibracion WHERE partido_id NOT IN (SELECT id FROM partido)"))
    op.create_foreign_key(FK, "calibracion", "partido", ["partido_id"], ["id"],
                          ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint(FK, "calibracion", type_="foreignkey")
