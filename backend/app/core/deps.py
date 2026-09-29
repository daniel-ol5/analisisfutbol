"""Dependencias compartidas: sesión, usuario autenticado y control de rol."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decodificar

esquema = HTTPBearer(auto_error=False)

Db = Annotated[AsyncSession, Depends(get_db)]


class UsuarioActual:
    """Identidad del que hace la petición, extraída del token."""

    def __init__(self, id: int, club_id: int, rol: str):
        self.id = id
        self.club_id = club_id
        self.rol = rol


async def usuario_actual(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema)],
) -> UsuarioActual:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de acceso")

    payload = decodificar(cred.credentials)
    if payload is None or payload.get("tipo") != "acceso":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")

    return UsuarioActual(
        id=int(payload["sub"]),
        club_id=int(payload["club"]),
        rol=str(payload["rol"]),
    )


Actual = Annotated[UsuarioActual, Depends(usuario_actual)]


def requiere_rol(*roles: str):
    """Restringe un endpoint a ciertos roles.

    Uso:
        @router.post("/", dependencies=[Depends(requiere_rol("ADMIN"))])
    """

    async def verificar(usuario: Actual) -> UsuarioActual:
        if usuario.rol not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requiere uno de estos roles: {', '.join(roles)}",
            )
        return usuario

    return verificar
