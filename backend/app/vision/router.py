"""Endpoints de Visión por Computadora  —  CU-18 … CU-29.

Casos de uso de este paquete:
    CU-18  Consultar guía de montaje de cámara
    CU-19  Calibrar cámara
    CU-20  Registrar medidas de la cancha
    CU-21  Validar error de calibración
    CU-22  Reutilizar calibración previa
    CU-23  Corregir distorsión del lente
    CU-24  Detectar y seguir jugadores y balón   (lo ejecuta el worker)
    CU-25  Clasificar jugadores por equipo       (lo ejecuta el worker)
    CU-26  Proyectar posiciones al plano          (lo ejecuta el worker)
    CU-27  Procesar video grabado
    CU-28  Cargar video de partido
    CU-29  Gestionar versiones del modelo

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="Comprobación del paquete")
async def ping() -> dict[str, str]:
    return {"paquete": "vision", "casos_de_uso": "CU-18 … CU-29", "estado": "pendiente"}
