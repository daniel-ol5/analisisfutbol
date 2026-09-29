"""Endpoints de Análisis Táctico  —  CU-40 … CU-48.

Casos de uso de este paquete:
    CU-40  Visualizar panel del partido en vivo
    CU-41  Visualizar plano 2D de posiciones
    CU-42  Consultar posesión y circulación
    CU-43  Consultar métricas físicas por jugador
    CU-44  Consultar mapas de calor
    CU-45  Consultar métricas tácticas colectivas
    CU-46  Consultar evolución por intervalos
    CU-47  Consultar línea de tiempo del partido
    CU-48  Consultar red de pases

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="Comprobación del paquete")
async def ping() -> dict[str, str]:
    return {"paquete": "analisis", "casos_de_uso": "CU-40 … CU-48", "estado": "pendiente"}
