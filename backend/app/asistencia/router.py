"""Endpoints de Asistencia y Reportes  —  CU-49 … CU-58.

Responsables segun el Sprint Planning:
    CU-49              motor de reglas y catalogo  · S4 · Daniel
    CU-50, CU-51       recomendaciones y valoracion · S4 · Alejandra
    CU-52, CU-53, CU-54 alertas, push y catalogo    · S4 · Araceli
    CU-55, CU-56       informes y exportacion       · S4 · Jhon
"""

from fastapi import APIRouter, Depends, Query, Response, status

from app.asistencia import service, valoracion
from app.asistencia.schemas import (
    DispositivoRegistrar,
    FormatoExportacion,
    Informe,
    PruebaRegla,
    Recomendacion,
    Regla,
    ReglaCrear,
    ReglaEditar,
    ResultadoPrueba,
    Valoracion,
)
from app.core.deps import Actual, Db, requiere_rol
from app.core.pendiente import RESPUESTA_501, pendiente

router = APIRouter()


# ---------------- CU-49, CU-54 · Reglas tacticas ----------------

@router.get("/reglas", response_model=list[Regla],
            summary="CU-54 · Listar el catalogo de reglas del club mas las globales",
            description="`activa` es la activacion PARA EL CLUB del usuario: una regla global "
                        "puede estar desactivada solo para su club. `activas` filtra por ese valor.")
async def listar_reglas(usuario: Actual, db: Db, activas: bool | None = None) -> list[Regla]:
    return await service.listar_reglas(db, usuario, activas)


# T-092: actores "Administrador del Club, Director Tecnico".
_GESTIONAN_REGLAS = [Depends(requiere_rol("ADMIN", "DT"))]


@router.post("/reglas", response_model=Regla, status_code=status.HTTP_201_CREATED,
             dependencies=_GESTIONAN_REGLAS,
             responses={403: {"description": "Solo ADMIN o DT"},
                        422: {"description": "Condicion o plantilla invalida, o metrica desconocida"}},
             summary="CU-54 · Crear una regla propia del club")
async def crear_regla(datos: ReglaCrear, usuario: Actual, db: Db) -> Regla:
    return await service.crear_regla(db, usuario, datos)


@router.patch("/reglas/{regla_id}", response_model=Regla,
              dependencies=_GESTIONAN_REGLAS,
              responses={403: {"description": "Solo ADMIN o DT; de una regla global solo se "
                                              "puede cambiar `activa`"},
                         404: {"description": "Regla inexistente o de otro club"},
                         422: {"description": "Condicion o plantilla invalida, o metrica desconocida"}},
              summary="CU-54 · Editar, activar o desactivar una regla",
              description="T-092: activar o desactivar surte efecto en la siguiente evaluacion "
                          "del motor, sin desplegar. En una regla global vale solo para el club "
                          "del usuario.")
async def editar_regla(regla_id: int, datos: ReglaEditar, usuario: Actual, db: Db) -> Regla:
    return await service.editar_regla(db, usuario, regla_id, datos)


@router.post("/reglas/{regla_id}/probar", response_model=ResultadoPrueba,
             dependencies=_GESTIONAN_REGLAS,
             responses={403: {"description": "Solo ADMIN o DT"},
                        404: {"description": "Regla o partido inexistente, o de otro club"}},
             summary="CU-54 · Probar una regla contra un partido ya registrado",
             description="Reproduce las posiciones guardadas del partido con el mismo motor y "
                         "la misma cadencia que en vivo (una evaluacion cada 5 s), respetando el "
                         "cooldown. Se puede probar una regla desactivada. No guarda nada.")
async def probar_regla(regla_id: int, datos: PruebaRegla, usuario: Actual, db: Db) -> ResultadoPrueba:
    return await service.probar_regla(db, usuario, regla_id, datos)


# ---------------- CU-50, CU-51, CU-52 · Recomendaciones ----------------

@router.get("/partidos/{partido_id}/recomendaciones", response_model=list[Recomendacion],
            responses={404: {"description": "Partido inexistente o de otro club"}},
            summary="CU-50 · Recomendaciones activas, maximo 3 y priorizadas")
async def recomendaciones(partido_id: int, usuario: Actual, db: Db,
                          solo_activas: bool = Query(True,
                              description="True devuelve como maximo las 3 de mayor prioridad")
                          ) -> list[Recomendacion]:
    return await service.listar_recomendaciones(db, usuario, partido_id, solo_activas)


# T-090, T-091 (Alejandra): quien ve las recomendaciones en el panel las valora.
PUEDEN_VALORAR = Depends(requiere_rol("ADMIN", "DT", "ANALISTA"))
_RESPUESTAS_RECOMENDACION = {
    403: {"description": "Requiere rol ADMIN, DT o ANALISTA"},
    404: {"description": "Recomendacion inexistente o de un partido de otro club"},
}


@router.post("/recomendaciones/{recomendacion_id}/valorar", response_model=Recomendacion,
             dependencies=[PUEDEN_VALORAR],
             responses={**_RESPUESTAS_RECOMENDACION,
                        409: {"description": "La recomendacion ya fue valorada"}},
             summary="CU-51 · Marcar util, no util o aplicada",
             description=(
                 "T-091. Util: queda VISTA (sigue activa). No util: DESCARTADA. Aplicada: "
                 "APLICADA, con `util` = true si no se indica. Las dos ultimas salen de las "
                 "activas. Una sola valoracion por recomendacion."
             ))
async def valorar(recomendacion_id: int, datos: Valoracion, usuario: Actual, db: Db) -> Recomendacion:
    return await valoracion.valorar(db, usuario, recomendacion_id, datos)


@router.post("/recomendaciones/{recomendacion_id}/vista", response_model=Recomendacion,
             dependencies=[PUEDEN_VALORAR],
             responses=_RESPUESTAS_RECOMENDACION,
             summary="CU-50 · Marcar una recomendacion como vista",
             description=(
                 "T-090. Lo llama el cliente la primera vez que la muestra: estado VISTA y "
                 "`vista_en`. Idempotente; no cambia una recomendacion ya valorada."
             ))
async def marcar_vista(recomendacion_id: int, usuario: Actual, db: Db) -> Recomendacion:
    return await valoracion.marcar_vista(db, usuario, recomendacion_id)


@router.get("/partidos/{partido_id}/alertas", response_model=list[Recomendacion],
            responses=RESPUESTA_501,
            summary="CU-52 · Alertas de fatiga y riesgo de expulsion")
async def alertas(partido_id: int, usuario: Actual, db: Db) -> list[Recomendacion]:
    # Regla: no se genera alerta de fatiga para jugadores que entraron hace menos de 15 minutos.
    pendiente("CU-52", "Sprint 4", "Araceli")


# ---------------- CU-53 · Notificaciones ----------------

@router.post("/dispositivos", status_code=status.HTTP_204_NO_CONTENT,
             summary="CU-53 · Registrar el token del dispositivo para recibir push")
async def registrar_dispositivo(
    datos: DispositivoRegistrar, usuario: Actual, db: Db
) -> None:
    await service.registrar_dispositivo(db, usuario, datos)


# ---------------- CU-55, CU-56 · Informes ----------------

@router.post("/partidos/{partido_id}/informe", response_model=Informe,
             status_code=status.HTTP_202_ACCEPTED,
             responses=RESPUESTA_501,
             summary="CU-55 · Generar el informe post-partido en segundo plano")
async def generar_informe(partido_id: int, usuario: Actual, db: Db) -> Informe:
    pendiente("CU-55", "Sprint 4", "Jhon")


@router.get("/informes/{informe_id}", response_model=Informe,
            responses=RESPUESTA_501,
            summary="CU-55 · Estado y descarga del informe")
async def ver_informe(informe_id: int, usuario: Actual, db: Db) -> Informe:
    pendiente("CU-55", "Sprint 4", "Jhon")


@router.get("/partidos/{partido_id}/exportar",
            summary="CU-56 · Exportar metricas a CSV",
            responses={**RESPUESTA_501,
                       200: {"content": {"text/csv": {}}, "description": "Archivo CSV en UTF-8"}})
async def exportar(partido_id: int, usuario: Actual, db: Db,
                   formato: FormatoExportacion = FormatoExportacion.METRICAS_EQUIPO) -> Response:
    pendiente("CU-56", "Sprint 4", "Jhon")
