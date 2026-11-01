"""Configuración de la aplicación, leída del entorno."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    proyecto: str = "Área Técnica"
    version: str = "0.1.0"

    database_url: str = "sqlite+aiosqlite:///./areatecnica.db"

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

    @property
    def origenes(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
