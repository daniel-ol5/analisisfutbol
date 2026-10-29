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
    LogoutInput,
    NuevoUsuario,
    RefreshTokenInput,
    RegistroClub,
    Sesion,
    UsuarioEditar,
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


@router.post("/refresh", response_model=Sesion,
             summary="CU-02 · Refrescar token con rotación")
async def refresh(datos: RefreshTokenInput, db: Db) -> Sesion:
    usuario = await service.refrescar_token(db, datos.refresh_token)
    return _sesion(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT,
             summary="CU-03 · Cerrar sesión")
async def logout(usuario: Actual, db: Db, datos: LogoutInput | None = None) -> None:
    await service.cerrar_sesion(
        db,
        usuario_id=usuario.id,
        jti_acceso=usuario.jti,
        refresh_token=datos.refresh_token if datos else None,
    )
    return None


@router.get("/yo", response_model=UsuarioOut,
            summary="Datos del usuario autenticado")
async def yo(usuario: Actual, db: Db) -> UsuarioOut:
    actual = await service.obtener_usuario_actual(db, usuario)
    return UsuarioOut.model_validate(actual)


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(requiere_rol("ADMIN"))],
             summary="CU-04 · Crear usuario del club")
async def crear_usuario(datos: NuevoUsuario, usuario: Actual, db: Db) -> UsuarioOut:
    nuevo = await service.crear_usuario(db, usuario, datos)
    return UsuarioOut.model_validate(nuevo)


@router.get("/usuarios", response_model=list[UsuarioOut],
            dependencies=[Depends(requiere_rol("ADMIN"))],
            summary="CU-04 · Listar usuarios del club")
async def listar_usuarios(usuario: Actual, db: Db) -> list[UsuarioOut]:
    usuarios = await service.listar_usuarios(db, usuario)
    return [UsuarioOut.model_validate(u) for u in usuarios]


@router.get("/usuarios/{usuario_id}", response_model=UsuarioOut,
            dependencies=[Depends(requiere_rol("ADMIN"))],
            summary="CU-04 · Consultar usuario del club")
async def ver_usuario(usuario_id: int, usuario: Actual, db: Db) -> UsuarioOut:
    u = await service.obtener_usuario(db, usuario.club_id, usuario_id)
    return UsuarioOut.model_validate(u)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut,
              dependencies=[Depends(requiere_rol("ADMIN"))],
              summary="CU-04 · Editar usuario del club")
async def editar_usuario(
    usuario_id: int, datos: UsuarioEditar, usuario: Actual, db: Db
) -> UsuarioOut:
    u = await service.editar_usuario(
        db, usuario.club_id, usuario_id, datos, autor_id=usuario.id
    )
    return UsuarioOut.model_validate(u)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(requiere_rol("ADMIN"))],
               summary="CU-04 · Dar de baja usuario del club")
async def eliminar_usuario(usuario_id: int, usuario: Actual, db: Db) -> None:
    await service.eliminar_usuario(
        db, usuario.club_id, usuario_id, autor_id=usuario.id
    )
    return None
