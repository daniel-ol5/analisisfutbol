"""Endpoints de Gestion Deportiva  —  CU-09 … CU-17.

Contrato congelado en el Sprint 1. Los endpoints estan declarados con su forma
de entrada y salida; devuelven 501 hasta que se implementen.

Responsables segun el Sprint Planning:
    CU-09, CU-10  equipos e indumentaria   · S2 · Daniel
    CU-11, CU-12  jugadores e importacion  · S2 · Alex
    CU-13 a CU-16 competiciones y partidos · S2 · Susana
    CU-17         alineacion y formacion   · S2 · Araceli
"""

from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import Response

from app.core.deps import Actual, Db
from app.core.pendiente import RESPUESTA_501, pendiente
from app.deportivo import service
from app.deportivo.schemas import (
    Alineacion,
    AlineacionGuardar,
    AvisoColores,
    Cancelacion,
    Competicion,
    CompeticionCrear,
    Equipo,
    EquipoCrear,
    EquipoEditar,
    EstadoPartido,
    Jugador,
    JugadorCrear,
    JugadorEditar,
    Partido,
    PartidoCrear,
    PartidoEditar,
    ResultadoImportacion,
)

router = APIRouter(responses=RESPUESTA_501)


# ---------------- CU-09, CU-10 · Equipos ----------------

@router.get("/equipos", response_model=list[Equipo], summary="CU-09 · Listar equipos del club")
async def listar_equipos(usuario: Actual, db: Db, activos: bool = True) -> list[Equipo]:
    return await service.listar_equipos(db, usuario, activos=activos)


@router.post("/equipos", response_model=Equipo, status_code=status.HTTP_201_CREATED,
             summary="CU-09 · Crear equipo")
async def crear_equipo(datos: EquipoCrear, usuario: Actual, db: Db) -> Equipo:
    return await service.crear_equipo(db, usuario, datos)


@router.get("/equipos/{equipo_id}", response_model=Equipo, summary="CU-09 · Ver equipo")
async def ver_equipo(equipo_id: int, usuario: Actual, db: Db) -> Equipo:
    return await service.ver_equipo(db, usuario, equipo_id)


@router.patch("/equipos/{equipo_id}", response_model=Equipo, summary="CU-09 · Editar equipo")
async def editar_equipo(equipo_id: int, datos: EquipoEditar, usuario: Actual, db: Db) -> Equipo:
    return await service.editar_equipo(db, usuario, equipo_id, datos)


@router.delete("/equipos/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="CU-09 · Desactivar equipo (baja logica)")
async def desactivar_equipo(equipo_id: int, usuario: Actual, db: Db) -> None:
    await service.desactivar_equipo(db, usuario, equipo_id)
    return None


@router.get("/equipos/{equipo_id}/colores/verificar", response_model=AvisoColores,
            summary="CU-10 · Verificar si dos equipos tienen colores demasiado similares")
async def verificar_colores(equipo_id: int, color_rival: str, usuario: Actual, db: Db) -> AvisoColores:
    return await service.verificar_colores_equipo(db, usuario, equipo_id, color_rival)


# ---------------- CU-11, CU-12 · Jugadores ----------------

@router.get("/equipos/{equipo_id}/jugadores", response_model=list[Jugador],
            summary="CU-11 · Listar plantel de un equipo")
async def listar_jugadores(equipo_id: int, usuario: Actual, db: Db,
                           activos: bool = True,
                           orden: str = Query("dorsal", pattern="^(dorsal|posicion|apellido)$")) -> list[Jugador]:
    return await service.listar_jugadores(db, usuario, equipo_id, activos=activos, orden=orden)


@router.post("/jugadores", response_model=Jugador, status_code=status.HTTP_201_CREATED,
             summary="CU-11 · Crear jugador")
async def crear_jugador(datos: JugadorCrear, usuario: Actual, db: Db) -> Jugador:
    return await service.crear_jugador(db, usuario, datos)


@router.get("/jugadores/{jugador_id}", response_model=Jugador, summary="CU-11 · Ver ficha de jugador")
async def ver_jugador(jugador_id: int, usuario: Actual, db: Db) -> Jugador:
    return await service.ver_jugador(db, usuario, jugador_id)


@router.patch("/jugadores/{jugador_id}", response_model=Jugador, summary="CU-11 · Editar jugador")
async def editar_jugador(jugador_id: int, datos: JugadorEditar, usuario: Actual, db: Db) -> Jugador:
    return await service.editar_jugador(db, usuario, jugador_id, datos)


@router.delete("/jugadores/{jugador_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="CU-11 · Dar de baja un jugador (conserva su historial)")
async def baja_jugador(jugador_id: int, usuario: Actual, db: Db) -> None:
    await service.baja_jugador(db, usuario, jugador_id)
    return None


@router.get("/equipos/{equipo_id}/jugadores/plantilla",
            summary="CU-12 · Descargar plantilla CSV para importar un plantel")
async def descargar_plantilla_jugadores(equipo_id: int, usuario: Actual) -> Response:
    contenido = service.generar_plantilla_csv_jugadores()
    return Response(
        content="﻿" + contenido,  # BOM: asi Excel/Sheets detectan UTF-8 en vez de leer Latin-1
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla_jugadores.csv"},
    )


@router.get("/equipos/{equipo_id}/jugadores/exportar",
            summary="CU-12 · Exportar el plantel actual a CSV")
async def exportar_jugadores_csv(equipo_id: int, usuario: Actual, db: Db,
                                 activos: bool = True,
                                 orden: str = Query("dorsal", pattern="^(dorsal|posicion|apellido)$"),
                                 ) -> Response:
    contenido = await service.exportar_jugadores_csv(db, usuario, equipo_id, activos=activos, orden=orden)
    return Response(
        content="﻿" + contenido,  # BOM: asi Excel/Sheets detectan UTF-8 en vez de leer Latin-1
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=plantel_equipo_{equipo_id}.csv"},
    )


@router.post("/equipos/{equipo_id}/jugadores/importar", response_model=ResultadoImportacion,
             summary="CU-12 · Importar plantel desde CSV")
async def importar_plantel(equipo_id: int, archivo: UploadFile, usuario: Actual, db: Db,
                           confirmar: bool = Query(False, description="False devuelve la vista previa sin guardar")
                           ) -> ResultadoImportacion:
    contenido = await archivo.read()
    return await service.importar_plantel(db, usuario, equipo_id, contenido, confirmar=confirmar)


# ---------------- CU-13 · Competiciones ----------------

@router.get("/competiciones", response_model=list[Competicion], summary="CU-13 · Listar competiciones")
async def listar_competiciones(usuario: Actual, db: Db) -> list[Competicion]:
    pendiente("CU-13", "Sprint 2", "Susana")


@router.post("/competiciones", response_model=Competicion, status_code=status.HTTP_201_CREATED,
             summary="CU-13 · Crear competicion")
async def crear_competicion(datos: CompeticionCrear, usuario: Actual, db: Db) -> Competicion:
    pendiente("CU-13", "Sprint 2", "Susana")


# ---------------- CU-14, CU-15, CU-16 · Partidos ----------------

@router.get("/partidos", response_model=list[Partido], summary="CU-15 · Agenda de partidos")
async def listar_partidos(usuario: Actual, db: Db,
                          equipo_id: int | None = None,
                          competicion_id: int | None = None,
                          estado: EstadoPartido | None = None,
                          desde: str | None = Query(None, description="Fecha ISO"),
                          hasta: str | None = None) -> list[Partido]:
    pendiente("CU-15", "Sprint 2", "Susana")


@router.post("/partidos", response_model=Partido, status_code=status.HTTP_201_CREATED,
             summary="CU-14 · Programar partido")
async def programar_partido(datos: PartidoCrear, usuario: Actual, db: Db) -> Partido:
    pendiente("CU-14", "Sprint 2", "Susana")


@router.get("/partidos/{partido_id}", response_model=Partido, summary="CU-15 · Ver partido")
async def ver_partido(partido_id: int, usuario: Actual, db: Db) -> Partido:
    pendiente("CU-15", "Sprint 2", "Susana")


@router.patch("/partidos/{partido_id}", response_model=Partido,
              summary="CU-16 · Reprogramar partido (solo si esta PROGRAMADO)")
async def reprogramar_partido(partido_id: int, datos: PartidoEditar, usuario: Actual, db: Db) -> Partido:
    pendiente("CU-16", "Sprint 2", "Susana")


@router.post("/partidos/{partido_id}/cancelar", response_model=Partido,
             summary="CU-16 · Cancelar partido")
async def cancelar_partido(partido_id: int, datos: Cancelacion, usuario: Actual, db: Db) -> Partido:
    pendiente("CU-16", "Sprint 2", "Susana")


# ---------------- CU-17 · Alineacion ----------------

@router.get("/partidos/{partido_id}/alineacion", response_model=Alineacion,
            summary="CU-17 · Ver alineacion del partido")
async def ver_alineacion(partido_id: int, usuario: Actual, db: Db) -> Alineacion:
    pendiente("CU-17", "Sprint 2", "Araceli")


@router.put("/partidos/{partido_id}/alineacion", response_model=Alineacion,
            summary="CU-17 · Guardar alineacion y formacion")
async def guardar_alineacion(partido_id: int, datos: AlineacionGuardar,
                             usuario: Actual, db: Db) -> Alineacion:
    pendiente("CU-17", "Sprint 2", "Araceli")
