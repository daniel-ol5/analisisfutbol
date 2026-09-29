"""Aislamiento de datos entre clubes  —  Pb-03.

Requisito de seguridad transversal: un club nunca puede ver datos de otro.

La regla del proyecto es que **ninguna consulta se escribe a mano sin pasar por
acá**. Repetir `.where(Modelo.club_id == usuario.club_id)` en cada endpoint es
exactamente como se filtran datos entre clubes sin querer: alcanza con que una
sola persona se olvide una vez.
"""

from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, select

from app.core.database import Base
from app.core.deps import UsuarioActual

T = TypeVar("T", bound=Base)


def del_club(modelo: type[T], usuario: UsuarioActual) -> Select[tuple[T]]:
    """Consulta base de un modelo, ya filtrada por el club del usuario.

        stmt = del_club(Equipo, usuario)
        equipos = (await db.execute(stmt)).scalars().all()
    """
    return select(modelo).where(modelo.club_id == usuario.club_id)


def verificar_pertenencia(obj: T | None, usuario: UsuarioActual) -> T:
    """Valida que el objeto exista y sea del club del usuario.

    Devuelve 404 y no 403 a propósito: un 403 confirmaría que el recurso existe
    en otro club, que es justamente lo que no queremos revelar.
    """
    if obj is None or getattr(obj, "club_id", None) != usuario.club_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
    return obj
