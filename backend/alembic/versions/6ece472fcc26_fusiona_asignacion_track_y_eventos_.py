"""fusiona asignacion_track y eventos_manuales

Fusión sin cambios de esquema: T-067 (asignacion_track, Jhon) y T-066
(evento_manual, Susana) partieron de cabezas distintas y main quedó con dos.

Revision ID: 6ece472fcc26
Revises: a4d9e2b71c63, e9c1b7f4a260
Create Date: 2026-11-09 21:47:51.632140

"""
from collections.abc import Sequence

revision: str = "6ece472fcc26"
down_revision: str | Sequence[str] | None = ("a4d9e2b71c63", "e9c1b7f4a260")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
