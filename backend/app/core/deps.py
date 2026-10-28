"""Dependencias compartidas: sesión, usuario autenticado y control de rol."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decodificar
from app.seguridad.models import TokenRevocado, Usuario

esquema = HTTPBearer(auto_error=False)

Db = Annotated[AsyncSession, Depends(get_db)]


class UsuarioActual:
    """Identidad del que hace la petición, extraída del token."""

    def __init__(self, id: int, club_id: int, rol: str, jti: str = ""):
        self.id = id
        self.club_id = club_id
        self.rol = rol
        self.jti = jti


async def usuario_actual(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema)],
    db: Db,
) -> UsuarioActual:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de acceso")

    payload = decodificar(cred.credentials)
    if payload is None or payload.get("tipo") != "acceso":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")

    jti = payload.get("jti")
    if jti:
        q = await db.execute(select(TokenRevocado).where(TokenRevocado.jti == jti))
        if q.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revocado")

    # CU-05: un cambio de contraseña sube la versión y cierra las sesiones viejas.
    q_ver = await db.execute(
        select(Usuario.version_sesion).where(Usuario.id == int(payload["sub"]))
    )
    version = q_ver.scalar_one_or_none()
    if version is not None and payload.get("ver", 0) != version:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "La sesión fue cerrada; inicia sesión de nuevo"
        )

    return UsuarioActual(
        id=int(payload["sub"]),
        club_id=int(payload["club"]),
        rol=str(payload["rol"]),
        jti=jti or "",
    )


Actual = Annotated[UsuarioActual, Depends(usuario_actual)]


def usuario_desde_token(token: str) -> UsuarioActual | None:
    """Identidad a partir de un token de acceso, o None si no es válido.

    Misma regla que `usuario_actual`, pero sin HTTP: la usan los WebSockets,
    que no pueden responder un 401 y cierran la conexión con su propio código.
    """
    payload = decodificar(token)
    if payload is None or payload.get("tipo") != "acceso":
        return None
    try:
        return UsuarioActual(
            id=int(payload["sub"]),
            club_id=int(payload["club"]),
            rol=str(payload["rol"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


class WorkerActual(UsuarioActual):
    """Identidad del worker de visión, extraída de un token de ingesta.

    Es un `UsuarioActual` para que `tenancy` lo trate igual (solo mira
    `club_id`). Su rol `WORKER` no coincide con ningún rol humano, así que
    `requiere_rol` nunca lo deja pasar.
    """

    def __init__(self, club_id: int, partido_id: int):
        super().__init__(id=0, club_id=club_id, rol="WORKER")
        self.partido_id = partido_id


def worker_desde_token(token: str) -> WorkerActual | None:
    """Identidad del worker, o None si el token no es de ingesta o no es válido."""
    payload = decodificar(token)
    if payload is None or payload.get("tipo") != "ingesta":
        return None
    try:
        return WorkerActual(club_id=int(payload["club"]), partido_id=int(payload["partido"]))
    except (KeyError, TypeError, ValueError):
        return None


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
