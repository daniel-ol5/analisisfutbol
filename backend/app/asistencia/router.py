"""Endpoints de Asistencia y Reportes  —  CU-49 … CU-58.

Casos de uso de este paquete:
    CU-49  Evaluar reglas tácticas
    CU-50  Recibir recomendación táctica
    CU-51  Registrar valoración de recomendación
    CU-52  Recibir alerta de estado de jugador
    CU-53  Recibir notificación push
    CU-54  Gestionar catálogo de reglas tácticas
    CU-55  Generar informe post-partido
    CU-56  Exportar métricas
    CU-57  Comparar partido con la temporada
    CU-58  Generar clips de jugadas clave

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="Comprobación del paquete")
async def ping() -> dict[str, str]:
    return {"paquete": "asistencia", "casos_de_uso": "CU-49 … CU-58", "estado": "pendiente"}
