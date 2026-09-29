"""Endpoints de Gestión Deportiva  —  CU-09 … CU-17.

Casos de uso de este paquete:
    CU-09  Gestionar equipos
    CU-10  Registrar indumentaria del equipo
    CU-11  Gestionar jugadores
    CU-12  Importar plantel desde archivo
    CU-13  Gestionar competiciones
    CU-14  Programar partido
    CU-15  Consultar agenda de partidos
    CU-16  Reprogramar o cancelar partido
    CU-17  Definir alineación y formación

El router traduce HTTP a llamadas de servicio y nada más: no toca la base de
datos directamente ni contiene lógica de negocio.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping", summary="Comprobación del paquete")
async def ping() -> dict[str, str]:
    return {"paquete": "deportivo", "casos_de_uso": "CU-09 … CU-17", "estado": "pendiente"}
