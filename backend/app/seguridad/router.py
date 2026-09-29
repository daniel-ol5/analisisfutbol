"""Endpoints de Seguridad y Administración  —  CU-01 … CU-08.

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter, Depends, status

from app.core.deps import Actual, Db, requiere_rol
from app.core.security import token_acceso, token_refresco
from app.seguridad import service
from app.seguridad.schemas import (
    Credenciales,
    NuevoUsuario,
    RegistroClub,
    Sesion,
    UsuarioOut,
)

router = APIRouter()


def _sesion(usuario) -> Sesion:
    return Sesion(
        access_token=token_acceso(usuario.id, usuario.club_id, usuario.rol),
        refresh_token=token_refresco(usuario.id),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.post("/registro", response_model=Sesion, status_code=status.HTTP_201_CREATED,
             summary="CU-01 · Registrar club y cuenta administradora")
async def registrar(datos: RegistroClub, db: Db) -> Sesion:
    usuario = await service.registrar_club(db, datos)
    return _sesion(usuario)


@router.post("/login", response_model=Sesion,
             summary="CU-02 · Iniciar sesión")
async def login(datos: Credenciales, db: Db) -> Sesion:
    usuario = await service.autenticar(db, datos.email, datos.password)
    return _sesion(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT,
             summary="CU-03 · Cerrar sesión")
async def logout(usuario: Actual) -> None:
    # TODO Pb-01: invalidar el refresh token en una lista negra persistida.
    # Borrarlo solo del cliente no alcanza como criterio de aceptación.
    return None


@router.get("/yo", response_model=UsuarioOut,
            summary="Datos del usuario autenticado")
async def yo(usuario: Actual, db: Db) -> UsuarioOut:
    usuarios = await service.listar_usuarios(db, usuario.club_id)
    return UsuarioOut.model_validate(next(u for u in usuarios if u.id == usuario.id))


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(requiere_rol("ADMIN"))],
             summary="CU-04 · Crear usuario del club")
async def crear_usuario(datos: NuevoUsuario, usuario: Actual, db: Db) -> UsuarioOut:
    nuevo = await service.crear_usuario(db, usuario.club_id, datos)
    return UsuarioOut.model_validate(nuevo)


@router.get("/usuarios", response_model=list[UsuarioOut],
            dependencies=[Depends(requiere_rol("ADMIN"))],
            summary="CU-04 · Listar usuarios del club")
async def listar_usuarios(usuario: Actual, db: Db) -> list[UsuarioOut]:
    usuarios = await service.listar_usuarios(db, usuario.club_id)
    return [UsuarioOut.model_validate(u) for u in usuarios]
