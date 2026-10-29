"""Endpoints de Seguridad y Administración  —  CU-01 … CU-08.

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.correo import enviar_correo
from app.core.deps import Actual, Db, requiere_rol
from app.core.security import token_acceso, token_refresco
from app.seguridad import service
from app.seguridad.schemas import (
    CambioPassword,
    Credenciales,
    LogoutInput,
    Mensaje,
    NuevoUsuario,
    PerfilEditar,
    PerfilOut,
    RefreshTokenInput,
    RegistroClub,
    RestablecerPassword,
    Sesion,
    SolicitudRecuperacion,
    UsuarioEditar,
    UsuarioOut,
)

router = APIRouter()


def _sesion(usuario) -> Sesion:
    return Sesion(
        access_token=token_acceso(
            usuario.id, usuario.club_id, usuario.rol, usuario.version_sesion
        ),
        refresh_token=token_refresco(usuario.id, usuario.version_sesion),
        usuario=UsuarioOut.model_validate(usuario),
    )


def _perfil(usuario) -> PerfilOut:
    """Requiere el usuario con `club` ya cargado (ver service.obtener_usuario_actual)."""
    return PerfilOut(
        **UsuarioOut.model_validate(usuario).model_dump(),
        club_nombre=usuario.club.nombre,
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


@router.post("/password/olvido", response_model=Mensaje,
             status_code=status.HTTP_202_ACCEPTED,
             summary="CU-06 · Pedir enlace para restablecer la contraseña",
             description="Responde lo mismo exista o no la cuenta, para no revelar qué "
                         "correos están registrados. El enlace vence en 1 hora.")
async def olvido_password(
    datos: SolicitudRecuperacion, db: Db, tareas: BackgroundTasks
) -> Mensaje:
    resultado = await service.solicitar_recuperacion(db, datos.email)
    if resultado is not None:
        usuario, token = resultado
        # En segundo plano: el tiempo de respuesta tampoco delata si existe.
        asunto, cuerpo = service.correo_recuperacion(usuario, token)
        tareas.add_task(enviar_correo, usuario.email, asunto, cuerpo)
    return Mensaje(
        detalle="Si el correo está registrado, te enviamos un enlace para "
                "restablecer la contraseña."
    )


@router.post("/password/restablecer", response_model=Sesion,
             summary="CU-06 · Restablecer la contraseña con el enlace recibido",
             description="Enlace de un solo uso. Cierra todas las sesiones abiertas y "
                         "devuelve una nueva para entrar de inmediato.")
async def restablecer_password(datos: RestablecerPassword, db: Db) -> Sesion:
    usuario = await service.restablecer_password(db, datos)
    return _sesion(usuario)


@router.get("/yo", response_model=PerfilOut,
            summary="CU-05 · Consultar perfil propio")
async def yo(usuario: Actual, db: Db) -> PerfilOut:
    actual = await service.obtener_usuario_actual(db, usuario)
    return _perfil(actual)


@router.patch("/yo", response_model=PerfilOut,
              summary="CU-05 · Editar nombre y apellido propios")
async def editar_perfil(datos: PerfilEditar, usuario: Actual, db: Db) -> PerfilOut:
    actual = await service.editar_perfil(db, usuario, datos)
    return _perfil(actual)


@router.post("/yo/password", response_model=Sesion,
             summary="CU-05 · Cambiar la contraseña propia",
             description="Exige la contraseña actual (403 si no coincide). Cierra todas "
                         "las sesiones abiertas y devuelve una nueva para este dispositivo.")
async def cambiar_password(datos: CambioPassword, usuario: Actual, db: Db) -> Sesion:
    actual = await service.cambiar_password(db, usuario, datos)
    return _sesion(actual)


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
