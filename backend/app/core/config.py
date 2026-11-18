"""Configuración de la aplicación, leída del entorno."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Claves que están escritas en el repositorio (valor por defecto, .env.example,
# docker-compose): cualquiera que lea el código puede firmar tokens con ellas.
CLAVES_PUBLICAS = {
    "cambiar-esta-clave-antes-de-desplegar",
    "clave-solo-para-desarrollo-no-usar-en-produccion",
}
ENTORNOS_PRODUCCION = {"production", "produccion", "prod"}
LARGO_MIN_CLAVE = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = ""
    """`development`, `production`... Con un entorno de producción el arranque exige una
    SECRET_KEY propia (T-105): con la del repositorio se podría falsificar un token de
    cualquier club y saltarse el aislamiento entre clubes."""

    proyecto: str = "Área Técnica"
    version: str = "0.1.0"

    database_url: str = ""
    """PostgreSQL 16: `postgresql+asyncpg://usuario:clave@host:5432/base`. Sin valor por
    defecto a propósito: la aplicación no arranca sin una base configurada."""
    db_null_pool: bool = False

    secret_key: str = "cambiar-esta-clave-antes-de-desplegar"
    algoritmo: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    ingesta_token_hours: int = 4   # T-033: alcanza para un partido con entretiempo y demoras
    reset_token_minutes: int = 60  # HU-52: vigencia del enlace de recuperación de contraseña

    cors_origins: str = "http://localhost:5173"

    # Base de los enlaces que van por correo (HU-52): apunta a la web.
    web_url: str = "http://localhost:5173"

    # Correo saliente (HU-52). Sin SMTP_HOST el correo no se envía: se escribe
    # en el log, para copiar el enlace en desarrollo. En producción, configurarlo.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_tls: bool = True
    smtp_usuario: str = ""
    smtp_password: str = ""
    smtp_remitente: str = "Área Técnica <no-responder@areatecnica.local>"

    # T-060: carga de video por partes. Disco local detrás de AlmacenVideos
    # (PROVISORIO hasta tener almacenamiento de objetos; ver vision/almacen.py).
    videos_dir: str = "./almacen/videos"
    video_max_bytes: int = 16 * 1024**3       # 16 GiB: un partido en 4K entra holgado
    video_max_trozo_bytes: int = 64 * 1024**2  # tope de cada PUT; el cliente usa 8 MiB
    vision_auto_worker: bool = False  # El worker externo toma la cola; evita competir en CPU.

    @model_validator(mode="after")
    def exigir_clave_propia_en_produccion(self) -> "Settings":
        if not self.secret_key.strip():
            raise ValueError("SECRET_KEY no puede estar vacía: defínela en el .env")
        if self.app_env.strip().lower() in ENTORNOS_PRODUCCION and (
            self.secret_key in CLAVES_PUBLICAS or len(self.secret_key) < LARGO_MIN_CLAVE
        ):
            raise ValueError(
                "SECRET_KEY debe ser propia y de al menos "
                f"{LARGO_MIN_CLAVE} caracteres cuando APP_ENV es de producción. Generar una con: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return self

    @property
    def origenes(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
