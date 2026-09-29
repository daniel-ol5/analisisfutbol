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

    cors_origins: str = "http://localhost:5173"

    @property
    def origenes(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
