"""Endpoints de Operación del Partido  —  CU-30 … CU-39.

Casos de uso de este paquete:
    CU-30  Iniciar y finalizar partido
    CU-31  Definir dirección de ataque
    CU-32  Capturar partido en vivo desde cámara
    CU-33  Sincronizar captura pendiente
    CU-34  Asignar jugadores a identificadores
    CU-35  Reasignar identificador
    CU-36  Registrar gol
    CU-37  Registrar tarjeta
    CU-38  Registrar sustitución
    CU-39  Supervisar calidad del procesamiento

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="Comprobación del paquete")
async def ping() -> dict[str, str]:
    return {"paquete": "partido", "casos_de_uso": "CU-30 … CU-39", "estado": "pendiente"}
