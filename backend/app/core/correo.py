"""Envío de correo saliente  —  HU-52.

Sin SMTP_HOST configurado el correo no sale: se escribe en el log. Así en
desarrollo se puede copiar el enlace sin levantar un servidor de correo.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger(__name__)


def _enviar_smtp(mensaje: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_usuario:
            smtp.login(settings.smtp_usuario, settings.smtp_password)
        smtp.send_message(mensaje)


async def enviar_correo(destino: str, asunto: str, cuerpo: str) -> None:
    """Envía un correo de texto. Nunca lanza: un fallo de envío queda en el log."""
    if not settings.smtp_host:
        log.warning(
            "SMTP_HOST sin configurar: el correo NO se envió.\n"
            "Para: %s\nAsunto: %s\n\n%s",
            destino, asunto, cuerpo,
        )
        return

    mensaje = EmailMessage()
    mensaje["From"] = settings.smtp_remitente
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    try:
        # smtplib es bloqueante: fuera del event loop.
        await asyncio.to_thread(_enviar_smtp, mensaje)
    except (OSError, smtplib.SMTPException):
        log.exception("No se pudo enviar el correo a %s", destino)
