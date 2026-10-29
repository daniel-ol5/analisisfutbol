"""Lógica de negocio de Seguridad.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se puede probar sin levantar el servidor.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import UsuarioActual
from app.core.security import decodificar, hashear, token_recuperacion, verificar
from app.core.tenancy import del_club, verificar_pertenencia
from app.seguridad.models import Club, Rol, TokenRecuperacion, TokenRevocado, Usuario
from app.seguridad.schemas import (
    CambioPassword,
    NuevoUsuario,
    PerfilEditar,
    RegistroClub,
    RestablecerPassword,
    UsuarioEditar,
)


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
    """Obtiene al usuario del token, con su club, sin permitir consultar otro club."""
    q = await db.execute(
        del_club(Usuario, actor)
        .where(Usuario.id == actor.id)
        .options(selectinload(Usuario.club))
    )
    return verificar_pertenencia(q.scalar_one_or_none(), actor)


async def editar_perfil(
    db: AsyncSession, actor: UsuarioActual, datos: PerfilEditar
) -> Usuario:
    """CU-05: el usuario cambia su propio nombre y/o apellido."""
    usuario = await obtener_usuario_actual(db, actor)
    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.apellido is not None:
        usuario.apellido = datos.apellido
    await db.commit()
    return usuario


async def cambiar_password(
    db: AsyncSession, actor: UsuarioActual, datos: CambioPassword
) -> Usuario:
    """CU-05: cambia la contraseña propia exigiendo la actual.

    Sube `version_sesion`, así que todos los tokens emitidos antes dejan de
    servir en cualquier dispositivo. El router devuelve una sesión nueva para
    que quien hizo el cambio siga conectado.
    """
    usuario = await obtener_usuario_actual(db, actor)

    # 403 y no 401: el token es válido, lo que falla es la clave actual; un 401
    # haría que el cliente cierre la sesión.
    if not verificar(datos.password_actual, usuario.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La contraseña actual es incorrecta")
    if datos.password_nueva == datos.password_actual:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La nueva contraseña debe ser distinta de la actual",
        )

    usuario.password_hash = hashear(datos.password_nueva)
    usuario.version_sesion += 1
    await db.commit()
    return usuario


async def listar_usuarios(db: AsyncSession, actor: UsuarioActual) -> list[Usuario]:
    """Lista usuarios usando el filtro multi-club centralizado."""
    q = await db.execute(del_club(Usuario, actor).order_by(Usuario.id))
    return list(q.scalars().all())


async def cerrar_sesion(
    db: AsyncSession,
    usuario_id: int,
    jti_acceso: str | None = None,
    refresh_token: str | None = None,
) -> None:
    """CU-03: invalida el token de acceso y/o de refresco en la lista negra persistida (Pb-01)."""
    if jti_acceso:
        q = await db.execute(select(TokenRevocado).where(TokenRevocado.jti == jti_acceso))
        if q.scalar_one_or_none() is None:
            db.add(TokenRevocado(jti=jti_acceso, usuario_id=usuario_id))

    if refresh_token:
        payload = decodificar(refresh_token)
        if payload and payload.get("tipo") == "refresco":
            jti_ref = payload.get("jti")
            if jti_ref:
                q_ref = await db.execute(
                    select(TokenRevocado).where(TokenRevocado.jti == jti_ref)
                )
                if q_ref.scalar_one_or_none() is None:
                    db.add(TokenRevocado(jti=jti_ref, usuario_id=usuario_id))

    await db.commit()


async def refrescar_token(db: AsyncSession, token_ref: str) -> Usuario:
    """CU-02: valida el token de refresco, lo revoca (rotación) y devuelve el usuario."""
    payload = decodificar(token_ref)
    if payload is None or payload.get("tipo") != "refresco":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token de refresco inválido o expirado"
        )

    jti = payload.get("jti")
    if jti:
        q = await db.execute(select(TokenRevocado).where(TokenRevocado.jti == jti))
        if q.scalar_one_or_none() is not None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "El token de refresco fue revocado"
            )

    usuario_id = int(payload["sub"])
    q_usr = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = q_usr.scalar_one_or_none()

    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado")
    if not usuario.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta está desactivada")
    if payload.get("ver", 0) != usuario.version_sesion:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "La sesión fue cerrada; inicia sesión de nuevo"
        )

    # Rotación: revocar el token de refresco usado
    if jti:
        db.add(TokenRevocado(jti=jti, usuario_id=usuario.id))
        await db.commit()

    return usuario


async def obtener_usuario(db: AsyncSession, club_id: int, usuario_id: int) -> Usuario:
    """CU-04: consulta un usuario asegurando el aislamiento por club."""
    q = await db.execute(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.club_id == club_id)
    )
    usuario = q.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return usuario


async def editar_usuario(
    db: AsyncSession,
    club_id: int,
    usuario_id: int,
    datos: UsuarioEditar,
    autor_id: int,
) -> Usuario:
    """CU-04: edita un usuario del club impidiendo auto-bloqueo del administrador."""
    usuario = await obtener_usuario(db, club_id, usuario_id)

    if usuario.id == autor_id:
        if datos.activo is False:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No puedes desactivar tu propia cuenta administradora",
            )
        if datos.rol is not None and datos.rol != Rol.ADMIN:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No puedes quitarte el rol de administrador a ti mismo",
            )

    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.apellido is not None:
        usuario.apellido = datos.apellido
    if datos.rol is not None:
        usuario.rol = datos.rol
    if datos.activo is not None:
        usuario.activo = datos.activo
    if datos.password is not None:
        usuario.password_hash = hashear(datos.password)

    await db.commit()
    await db.refresh(usuario)
    return usuario


async def eliminar_usuario(
    db: AsyncSession,
    club_id: int,
    usuario_id: int,
    autor_id: int,
) -> None:
    """CU-04: baja lógica (activo=False) de un usuario del club."""
    usuario = await obtener_usuario(db, club_id, usuario_id)

    if usuario.id == autor_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No puedes dar de baja tu propia cuenta administradora",
        )

    usuario.activo = False
    await db.commit()


# ---------- CU-06 Recuperar contraseña (HU-52) ----------

ENLACE_INVALIDO = "El enlace no es válido o ya venció. Pide uno nuevo."


def _anular_enlaces_pendientes(usuario_id: int, ahora: datetime):
    return (
        update(TokenRecuperacion)
        .where(
            TokenRecuperacion.usuario_id == usuario_id,
            TokenRecuperacion.usado_en.is_(None),
        )
        .values(usado_en=ahora)
    )


async def solicitar_recuperacion(
    db: AsyncSession, email: str
) -> tuple[Usuario, str] | None:
    """HU-52 · Criterio 1: genera un enlace de un solo uso y anula los anteriores.

    Devuelve None si no hay una cuenta activa con ese email. El router responde
    lo mismo en ambos casos para no revelar qué cuentas existen.
    """
    q = await db.execute(select(Usuario).where(Usuario.email == email))
    usuario = q.scalar_one_or_none()
    if usuario is None or not usuario.activo:
        return None

    ahora = datetime.now(UTC)
    await db.execute(_anular_enlaces_pendientes(usuario.id, ahora))
    token, jti = token_recuperacion(usuario.id)
    db.add(TokenRecuperacion(
        jti=jti,
        usuario_id=usuario.id,
        expira_en=ahora + timedelta(minutes=settings.reset_token_minutes),
    ))
    await db.commit()
    return usuario, token


def correo_recuperacion(usuario: Usuario, token: str) -> tuple[str, str]:
    """Asunto y cuerpo del correo con el enlace de recuperación."""
    enlace = f"{settings.web_url.rstrip('/')}/restablecer?token={token}"
    saludo = f"Hola {usuario.nombre}," if usuario.nombre else "Hola,"
    cuerpo = (
        f"{saludo}\n\n"
        "Recibimos un pedido para restablecer la contraseña de tu cuenta de "
        "Área Técnica. Para elegir una nueva, abre este enlace:\n\n"
        f"{enlace}\n\n"
        f"El enlace vence en {settings.reset_token_minutes} minutos y sirve una "
        "sola vez.\n\n"
        "Si no lo pediste tú, ignora este correo: tu contraseña no cambia."
    )
    return "Restablecer tu contraseña de Área Técnica", cuerpo


async def restablecer_password(db: AsyncSession, datos: RestablecerPassword) -> Usuario:
    """HU-52 · Criterios 2 y 3: guarda la nueva contraseña, anula todo enlace
    pendiente y cierra todas las sesiones abiertas.
    """
    payload = decodificar(datos.token)  # ya verifica firma y vencimiento
    if payload is None or payload.get("tipo") != "recuperacion":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, ENLACE_INVALIDO)

    usuario = await db.get(Usuario, int(payload["sub"]))
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, ENLACE_INVALIDO)

    # Marcar el enlace como usado en una sola sentencia condicional: si llegan
    # dos pedidos con el mismo enlace a la vez, solo uno lo consigue.
    ahora = datetime.now(UTC)
    marcado = await db.execute(
        update(TokenRecuperacion)
        .where(
            TokenRecuperacion.jti == payload.get("jti"),
            TokenRecuperacion.usuario_id == usuario.id,
            TokenRecuperacion.usado_en.is_(None),
        )
        .values(usado_en=ahora)
    )
    if marcado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, ENLACE_INVALIDO)

    await db.execute(_anular_enlaces_pendientes(usuario.id, ahora))
    usuario.password_hash = hashear(datos.password_nueva)
    usuario.version_sesion += 1
    await db.commit()
    return usuario
