"""Hashing de contraseñas y emisión/verificación de JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


# ---------- contraseñas ----------

def hashear(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar(password: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hash_guardado.encode())
    except ValueError:
        return False


# ---------- tokens ----------

def _crear_token(datos: dict[str, Any], expira: timedelta, tipo: str) -> str:
    payload = datos.copy()
    payload.update({"exp": datetime.now(UTC) + expira, "tipo": tipo})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algoritmo)


def token_acceso(usuario_id: int, club_id: int, rol: str) -> str:
    return _crear_token(
        {"sub": str(usuario_id), "club": club_id, "rol": rol},
        timedelta(minutes=settings.access_token_minutes),
        "acceso",
    )


def token_refresco(usuario_id: int) -> str:
    return _crear_token(
        {"sub": str(usuario_id)},
        timedelta(days=settings.refresh_token_days),
        "refresco",
    )


def decodificar(token: str) -> dict[str, Any] | None:
    """Devuelve el payload, o None si el token es inválido o expiró."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algoritmo])
    except jwt.PyJWTError:
        return None
