"""Esquemas de entrada y salida de Seguridad."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.seguridad.models import Rol

# ---------- CU-01 Registrar club ----------

class RegistroClub(BaseModel):
    nombre_club: str = Field(min_length=2, max_length=120)
    ciudad: str = Field(default="", max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # 72 = límite de bcrypt
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


# ---------- CU-04 Gestionar usuarios ----------

class NuevoUsuario(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    nombre: str = Field(default="", max_length=80)
    apellido: str = Field(default="", max_length=80)
    rol: Rol


class ClubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    ciudad: str
    activo: bool
