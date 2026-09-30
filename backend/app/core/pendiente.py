"""Marcador de endpoint declarado pero todavia no implementado.

El contrato de la API se congela en el Sprint 1 (Pb-01) para que Web y Movil
puedan generar mocks y trabajar en paralelo. Los endpoints existen en el
esquema OpenAPI con su forma de entrada y salida definida, pero devuelven 501
hasta que alguien los implemente en su sprint.

Al implementar uno: borrar la llamada a `pendiente()` y escribir la logica en
el `service.py` del paquete.
"""

from fastapi import HTTPException, status

RESPUESTA_501 = {
    501: {
        "description": "Declarado en el contrato, pendiente de implementacion",
        "content": {
            "application/json": {
                "example": {"detail": "CU-09 pendiente · Sprint 2 · responsable: Daniel"}
            }
        },
    }
}


def pendiente(cu: str, sprint: str, responsable: str = "a asignar"):
    """Corta la ejecucion indicando que caso de uso falta y quien lo tiene."""
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        f"{cu} pendiente · {sprint} · responsable: {responsable}",
    )
