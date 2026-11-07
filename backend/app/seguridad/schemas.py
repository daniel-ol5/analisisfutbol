"""Esquemas de entrada y salida de Seguridad."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.seguridad.models import Rol

# ---------- Política de contraseñas (HU-52 · Criterio 2) ----------

def _max_72_bytes(password: str) -> str:
    # bcrypt rechaza más de 72 bytes, y con acentos 72 caracteres pueden ocupar más.
    if len(password.encode()) > 72:
        raise ValueError(
            "La contraseña no puede ocupar más de 72 bytes "
            "(los acentos y símbolos ocupan más de uno)"
        )
    return password


# Una sola regla para toda contraseña nueva: registro, alta, cambio y recuperación.
PasswordNueva = Annotated[
    str, Field(min_length=8, max_length=72), AfterValidator(_max_72_bytes)
]


# ---------- CU-01 Registrar club ----------

class RegistroClub(BaseModel):
    nombre_club: str = Field(min_length=2, max_length=120)
    ciudad: str = Field(default="", max_length=80)
    email: EmailStr
    password: PasswordNueva
    nombre: str = Field(default="", max_length=80)
    apellido: str = Field(default="", max_length=80)


# ---------- CU-02 Iniciar sesión ----------

class Credenciales(BaseModel):
    email: EmailStr
    password: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    club_id: int
    email: EmailStr
    nombre: str
    apellido: str
    rol: Rol
    activo: bool


class Sesion(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


# ---------- CU-02 / CU-03 Refresco y Cierre de Sesión ----------

class RefreshTokenInput(BaseModel):
    refresh_token: str


class LogoutInput(BaseModel):
    refresh_token: str | None = None


# ---------- CU-04 Gestionar usuarios ----------

class NuevoUsuario(BaseModel):
    email: EmailStr
    password: PasswordNueva
    nombre: str = Field(default="", max_length=80)
    apellido: str = Field(default="", max_length=80)
    rol: Rol


class UsuarioEditar(BaseModel):
    nombre: str | None = Field(default=None, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)
    rol: Rol | None = None
    activo: bool | None = None
    password: PasswordNueva | None = None


# ---------- CU-05 Administrar perfil propio ----------

class PerfilOut(UsuarioOut):
    club_nombre: str


class PerfilEditar(BaseModel):
    """Solo nombre y apellido: email, rol y estado los administra el ADMIN (CU-04)."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _al_menos_un_campo(self) -> "PerfilEditar":
        if self.nombre is None and self.apellido is None:
            raise ValueError("Indica al menos el nombre o el apellido")
        return self


class CambioPassword(BaseModel):
    password_actual: str
    password_nueva: PasswordNueva


# ---------- CU-06 Recuperar contraseña (HU-52) ----------

class SolicitudRecuperacion(BaseModel):
    email: EmailStr


class RestablecerPassword(BaseModel):
    token: str
    password_nueva: PasswordNueva


class Mensaje(BaseModel):
    detalle: str


class ClubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    ciudad: str
    activo: bool
