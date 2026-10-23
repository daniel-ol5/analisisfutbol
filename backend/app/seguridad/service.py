"""Lógica de negocio de Seguridad.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se puede probar sin levantar el servidor.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import UsuarioActual
from app.core.security import hashear, verificar
from app.core.tenancy import del_club, verificar_pertenencia
from app.seguridad.models import Club, Rol, Usuario
from app.seguridad.schemas import NuevoUsuario, RegistroClub


async def _email_existe(db: AsyncSession, email: str) -> bool:
    q = await db.execute(select(Usuario).where(Usuario.email == email))
    return q.scalar_one_or_none() is not None


async def registrar_club(db: AsyncSession, datos: RegistroClub) -> Usuario:
    """CU-01: crea el club y su primer usuario administrador."""
    if await _email_existe(db, datos.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese email ya tiene una cuenta")

    club = Club(nombre=datos.nombre_club, ciudad=datos.ciudad)
    db.add(club)
    await db.flush()  # asigna club.id sin cerrar la transacción

    admin = Usuario(
        club_id=club.id,
        email=datos.email,
        password_hash=hashear(datos.password),
        nombre=datos.nombre,
        apellido=datos.apellido,
        rol=Rol.ADMIN,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def autenticar(db: AsyncSession, email: str, password: str) -> Usuario:
    """CU-02: valida credenciales.

    El error es genérico a propósito: distinguir «email inexistente» de
    «contraseña incorrecta» le revela a un atacante qué cuentas existen.
    """
    q = await db.execute(select(Usuario).where(Usuario.email == email))
    usuario = q.scalar_one_or_none()

    if usuario is None or not verificar(password, usuario.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    if not usuario.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta está desactivada")

    return usuario


async def crear_usuario(
    db: AsyncSession, actor: UsuarioActual, datos: NuevoUsuario
) -> Usuario:
    """CU-04: alta de usuario dentro del club de quien lo crea."""
    if await _email_existe(db, datos.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese email ya tiene una cuenta")

    usuario = Usuario(
        # El club nunca viene del cuerpo ni de un parametro libre: se deriva
        # exclusivamente de la identidad autenticada.
        club_id=actor.club_id,
        email=datos.email,
        password_hash=hashear(datos.password),
        nombre=datos.nombre,
        apellido=datos.apellido,
        rol=datos.rol,
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def obtener_usuario_actual(db: AsyncSession, actor: UsuarioActual) -> Usuario:
    """Obtiene al usuario del token sin permitir consultar otro club."""
    q = await db.execute(del_club(Usuario, actor).where(Usuario.id == actor.id))
    return verificar_pertenencia(q.scalar_one_or_none(), actor)


async def listar_usuarios(db: AsyncSession, actor: UsuarioActual) -> list[Usuario]:
    """Lista usuarios usando el filtro multi-club centralizado."""
    q = await db.execute(del_club(Usuario, actor).order_by(Usuario.id))
    return list(q.scalars().all())
