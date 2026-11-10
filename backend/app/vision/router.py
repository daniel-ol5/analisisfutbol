"""Endpoints de Vision por Computadora  —  CU-18 … CU-29.

Responsables segun el Sprint Planning:
    CU-19 a CU-21  calibracion y homografia  · S2 · Jhon
    CU-22, CU-23   calibracion previa y lente · S2 · Alejandra (T-035, T-036)
    CU-24 a CU-26  worker de vision          · S3 · Alex  (corre fuera de este backend)
    CU-27 a CU-29  video y modelos           · S3 · Araceli
"""

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    Form,
    Header,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core.deps import Actual, Db, requiere_rol
from app.core.pendiente import RESPUESTA_501
from app.partido.service import AlmacenPosiciones, obtener_almacen_posiciones
from app.vision import procesamiento, service, videos
from app.vision.almacen import AlmacenVideos, obtener_almacen_videos
from app.vision.schemas import (
    ActivarModelo,
    Calibracion,
    CalibracionGuardar,
    CalibracionIntrinseca,
    ErrorCalibracion,
    FinTrabajo,
    LanzarProceso,
    MensajeWorker,
    Modelo,
    ModeloCrear,
    ResultadosLote,
    Trabajo,
    Video,
    VideoIniciar,
)

router = APIRouter(responses=RESPUESTA_501)

# 422 de los dos POST de calibracion. Declarar `responses={422: ...}` REEMPLAZA el 422 que
# FastAPI genera solo, asi que el esquema estandar se vuelve a referenciar a mano
# (HTTPValidationError ya existe en components porque lo usan los demas endpoints).
RESPUESTA_422_CALIBRACION = {
    422: {
        "description": (
            "Datos invalidos. La validacion de Pydantic (formas, rangos, minimo de 8 puntos, "
            "misma cantidad de puntos) devuelve `detail` como LISTA de errores. Una homografia "
            "degenerada (puntos colineales, repetidos, matriz singular) devuelve `detail` como "
            "TEXTO con el motivo, y en POST /calibracion no se guarda nada"
        ),
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
            }
        },
    }
}


# ---------------- CU-19, CU-20, CU-21, CU-22 · Calibracion ----------------

@router.get("/partidos/{partido_id}/calibracion", response_model=Calibracion,
            summary="CU-19 · Ver la calibracion vigente del partido")
async def ver_calibracion(partido_id: int, usuario: Actual, db: Db) -> Calibracion:
    calibracion = await service.obtener_calibracion(db, usuario, partido_id)
    return Calibracion.model_validate(calibracion)


@router.post("/partidos/{partido_id}/calibracion", response_model=Calibracion,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             responses={200: {"model": Calibracion,
                              "description": "El partido ya tenia calibracion: se actualizo"},
                        **RESPUESTA_422_CALIBRACION},
             summary="CU-19, CU-20 · Calibrar camara y registrar medidas de cancha")
async def calibrar(partido_id: int, datos: CalibracionGuardar, usuario: Actual, db: Db,
                   response: Response) -> Calibracion:
    # 201 al crear, 200 al actualizar una calibracion existente (upsert).
    calibracion, creada = await service.guardar_calibracion(db, usuario, partido_id, datos)
    if not creada:
        response.status_code = status.HTTP_200_OK
    return Calibracion.model_validate(calibracion)


@router.post("/partidos/{partido_id}/calibracion/validar", response_model=ErrorCalibracion,
             responses=RESPUESTA_422_CALIBRACION,
             summary="CU-21 · Calcular el error de reproyeccion sin guardar")
async def validar_calibracion(partido_id: int, datos: CalibracionGuardar,
                              usuario: Actual) -> ErrorCalibracion:
    # Calculo puro: no consulta ni escribe la base, por eso no pide sesion ni rol.
    return service.validar_calibracion(datos)


@router.post("/partidos/{partido_id}/calibracion/detectar-ia",
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             summary="Detectar puntos clave de la cancha automáticamente con IA (YOLO Pose)")
async def detectar_calibracion_ia(
    partido_id: int,
    archivo: Annotated[UploadFile, File(...)],
    usuario: Actual,
    largo_m: Annotated[float, Form()] = 105.0,
    ancho_m: Annotated[float, Form()] = 68.0,
) -> dict[str, Any]:
    contenido = await archivo.read()
    return procesamiento.detectar_calibracion_con_ia(
        contenido,
        largo_m=largo_m,
        ancho_m=ancho_m,
    )


@router.get("/sedes/{sede}/calibracion-previa", response_model=Calibracion,
            responses={404: {"description": "No hay una calibracion valida previa del club "
                                            "en esa sede"}},
            summary="CU-22 · Recuperar una calibracion anterior de la misma sede")
async def calibracion_previa(sede: str, usuario: Actual, db: Db) -> Calibracion:
    """La calibracion valida mas reciente del club en un partido de esa sede (T-035).

    La sede se compara sin distinguir mayusculas ni espacios sobrantes. La
    respuesta trae `advertencia`: hay que verificar que la camara no se movio.
    Para usarla en el partido nuevo, enviar sus puntos y medidas en
    POST /partidos/{id}/calibracion.
    """
    calibracion = await service.calibracion_previa(db, usuario, sede)
    return Calibracion.model_validate(calibracion).model_copy(
        update={"advertencia": service.ADVERTENCIA_CAMARA_MOVIDA})



DESCRIPCION_INTRINSECA = """
Calibra la **camara y el lente** (no la cancha) con fotos de un tablero de ajedrez
impreso, rigido y plano. Se hace una vez por camara, lente y resolucion. **No
guarda nada**: devuelve los parametros para enviarlos en la calibracion de la cancha.

**Fotos:** entre 5 y 20, JPG o PNG, hasta 10 MB cada una, todas del mismo tamano y
con la misma resolucion con la que se va a filmar. El tablero entero en cada foto,
inclinado de distintas formas y llegando a las esquinas y bordes del cuadro, que es
donde mas deforma el lente. `columnas` y `filas` son las esquinas INTERIORES del
tablero (uno de 10 x 7 casillas tiene 9 x 6).

**Uso en dos pasos:**

1. `POST /api/vision/calibracion-intrinseca?columnas=9&filas=6` (multipart, campo
   `imagenes` repetido una vez por foto). Respuesta:

```json
{"matriz_camara": [[1012.4, 0, 960.7], [0, 1011.9, 541.2], [0, 0, 1]],
 "coef_distorsion": [-0.31, 0.11, 0.0004, -0.0003, -0.017],
 "tamano_imagen": [1920, 1080], "error_reproyeccion_px": 0.27, "imagenes_usadas": 18}
```

2. `POST /api/vision/partidos/{partido_id}/calibracion` con los puntos de la cancha
   y esos tres campos (los demas se pueden enviar tambien; se ignoran):

```json
{"puntos_imagen": [...], "puntos_cancha": [...], "largo_m": 100, "ancho_m": 64,
 "matriz_camara": [[1012.4, 0, 960.7], [0, 1011.9, 541.2], [0, 0, 1]],
 "coef_distorsion": [-0.31, 0.11, 0.0004, -0.0003, -0.017],
 "tamano_imagen": [1920, 1080]}
```

Con los tres campos, los `puntos_imagen` se corrigen antes de calcular la homografia
y el error de reproyeccion (CU-21) ya no crece cerca de las bandas.
"""


@router.post("/calibracion-intrinseca", response_model=CalibracionIntrinseca,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             responses={
                 403: {"description": "Requiere rol ADMIN o ANALISTA"},
                 413: {"description": "Alguna foto supera los 10 MB"},
                 422: {"description": (
                     "Menos de 5 o mas de 20 fotos, una foto ilegible, fotos de distinto "
                     "tamano, o el tablero se detecto en menos de 5 fotos")},
             },
             summary="CU-23 · Calibrar el lente con fotos de un tablero de ajedrez",
             description=DESCRIPCION_INTRINSECA)
async def calibracion_intrinseca(
    imagenes: Annotated[list[UploadFile], File(
        description="Fotos del tablero, de 5 a 20, JPG o PNG, hasta 10 MB cada una")],
    columnas: Annotated[int, Query(ge=3, le=30, description="Esquinas interiores por fila")] = 9,
    filas: Annotated[int, Query(ge=3, le=30, description="Esquinas interiores por columna")] = 6,
) -> CalibracionIntrinseca:
    if not service.MIN_FOTOS_TABLERO <= len(imagenes) <= service.MAX_FOTOS_TABLERO:
        raise HTTPException(422, (
            f"Hacen falta entre {service.MIN_FOTOS_TABLERO} y {service.MAX_FOTOS_TABLERO} "
            f"fotos del tablero (llegaron {len(imagenes)})"))
    fotos = []
    for i, imagen in enumerate(imagenes):
        datos = await imagen.read(service.MAX_BYTES_FOTO + 1)
        if len(datos) > service.MAX_BYTES_FOTO:
            raise HTTPException(413, f"La foto {i} supera los 10 MB")
        fotos.append(datos)
    # OpenCV tarda cientos de ms: fuera del event loop para no frenar a los demas
    resultado = await run_in_threadpool(service.calibrar_intrinseca, fotos, (columnas, filas))
    return CalibracionIntrinseca(**resultado.a_dict())

# ---------------- CU-29 · Modelos ----------------

@router.get("/modelos", response_model=list[Modelo], summary="CU-29 · Listar versiones del modelo")
async def listar_modelos(usuario: Actual, db: Db) -> list[Modelo]:
    modelos = await service.listar_modelos(db, usuario)
    return [Modelo.model_validate(m) for m in modelos]


@router.post("/modelos", response_model=Modelo, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             summary="CU-29 · Registrar una version entrenada")
async def registrar_modelo(datos: ModeloCrear, usuario: Actual, db: Db) -> Modelo:
    modelo = await service.registrar_modelo(db, usuario, datos)
    return Modelo.model_validate(modelo)


@router.post("/modelos/{modelo_id}/activar", response_model=Modelo,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             responses={409: {"description": "T-064: tiene metricas peores que la version "
                                             "activa. Para volver atras, enviar forzar=true "
                                             "con el motivo"}},
             summary="CU-29 · Activar una version (solo una activa por vez)",
             description=(
                 "El cuerpo es opcional. Sin cuerpo (o con forzar=false) se rechaza una version "
                 "con mAP o IDF1 peores que la activa (T-064). Con forzar=true y un motivo se "
                 "activa igual, y el motivo queda registrado (volver atras, T-059)."
             ))
async def activar_modelo(modelo_id: int, usuario: Actual, db: Db,
                         datos: Annotated[ActivarModelo | None, Body()] = None) -> Modelo:
    modelo = await service.activar_modelo(db, usuario, modelo_id, datos)
    return Modelo.model_validate(modelo)


# ---------------- CU-27, CU-28 · Video ----------------

AlmacenDep = Annotated[AlmacenVideos, Depends(obtener_almacen_videos)]

# CU-28: suben video el analista y el asistente (y el administrador).
PUEDEN_SUBIR = Depends(requiere_rol("ADMIN", "ANALISTA", "ASISTENTE"))

_RESPUESTA_404 = {404: {"description": "Partido o video inexistente, o de otro club"}}


@router.get("/partidos/{partido_id}/videos", response_model=list[Video],
            responses=_RESPUESTA_404,
            summary="CU-28 · Listar videos del partido (el más nuevo primero)")
async def listar_videos(partido_id: int, usuario: Actual, db: Db) -> list[Video]:
    return [Video.model_validate(v) for v in await videos.listar_videos(db, usuario, partido_id)]


@router.post("/partidos/{partido_id}/videos", response_model=Video,
             status_code=status.HTTP_201_CREATED,
             dependencies=[PUEDEN_SUBIR],
             responses={
                 **_RESPUESTA_404,
                 409: {"description": "El partido está cancelado"},
                 413: {"description": "El tamaño supera el máximo configurado"},
                 415: {"description": "Formato no soportado: se rechaza antes de subir nada"},
             },
             summary="CU-28 · Iniciar la carga por partes de un video (T-060)",
             description=(
                 "Paso 1 de 3. Declara el archivo sin enviarlo: valida extensión (.mp4, .mov, "
                 ".mkv), tipo MIME y tamaño, y crea el video en estado CARGANDO. Después se "
                 "envía el contenido por trozos con `PUT /videos/{id}/contenido`."
             ))
async def iniciar_carga(partido_id: int, datos: VideoIniciar, usuario: Actual, db: Db,
                        almacen: AlmacenDep) -> Video:
    video = await videos.iniciar_carga(db, usuario, partido_id, datos, almacen)
    return Video.model_validate(video)


@router.put("/videos/{video_id}/contenido", response_model=Video,
            dependencies=[PUEDEN_SUBIR],
            responses={
                **_RESPUESTA_404,
                400: {"description": "Content-Range ausente o inconsistente con el cuerpo"},
                409: {"description": "El trozo no empieza donde quedó la carga (ver "
                                     "`bytes_recibidos`), o la carga ya terminó"},
                413: {"description": "El trozo supera el máximo por envío"},
                415: {"description": "El primer trozo no tiene la firma del formato declarado"},
                416: {"description": "El trozo se pasa del final del archivo"},
            },
            openapi_extra={"requestBody": {
                "required": True,
                "content": {"application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}}},
            }},
            summary="CU-28 · Enviar un trozo del video (T-060)",
            description=(
                "Paso 2 de 3. El cuerpo son los bytes crudos del trozo y `Content-Range: "
                "bytes inicio-fin/total` dice cuáles son. Los trozos van en orden: cada uno "
                "empieza en `bytes_recibidos`. Para retomar una carga cortada, consultar "
                "`GET /videos/{id}` y seguir desde ahí. Con el último trozo el video se lee "
                "y queda SUBIDO (con duración, fps y resolución) o ERROR (con el motivo)."
            ))
async def enviar_trozo(video_id: int, request: Request, usuario: Actual, db: Db,
                       almacen: AlmacenDep,
                       content_range: Annotated[str | None, Header()] = None) -> Video:
    video = await videos.recibir_trozo(
        db, usuario, video_id, content_range, request.stream(), almacen
    )
    return Video.model_validate(video)


@router.get("/videos/{video_id}", response_model=Video,
            responses=_RESPUESTA_404,
            summary="CU-27, CU-28 · Estado de la carga y del procesamiento")
async def estado_video(video_id: int, usuario: Actual, db: Db) -> Video:
    return Video.model_validate(await videos.ver_video(db, usuario, video_id))


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[PUEDEN_SUBIR],
               responses=_RESPUESTA_404,
               summary="CU-28 · Eliminar un video del partido")
async def eliminar_video(video_id: int, usuario: Actual, db: Db,
                         almacen: AlmacenDep) -> None:
    await videos.eliminar_video(db, usuario, video_id, almacen)


# ---------------- CU-27 · Procesamiento diferido (T-061) ----------------

# CU-27 lo lanza el analista; el worker se autentica como ADMIN o ANALISTA.
PUEDEN_PROCESAR = Depends(requiere_rol("ADMIN", "ANALISTA"))

PosicionesDep = Annotated[AlmacenPosiciones, Depends(obtener_almacen_posiciones)]


@router.post("/videos/{video_id}/procesar", response_model=Video,
             dependencies=[PUEDEN_PROCESAR],
             responses={
                 **_RESPUESTA_404,
                 409: {"description": "Ya se está procesando, la carga no terminó, o el "
                                      "partido no tiene una calibración válida"},
             },
             summary="CU-27 · Lanzar el procesamiento en segundo plano (T-061)",
             description=(
                 "Deja el video PROCESANDO, en cola. Un worker externo con GPU lo toma, corre "
                 "el pipeline completo y va actualizando `progreso_pct`. Consultar el avance "
                 "con `GET /videos/{id}`."
             ))
async def procesar_video(video_id: int, datos: LanzarProceso, usuario: Actual, db: Db) -> Video:
    video = await procesamiento.lanzar(db, usuario, video_id, datos)
    procesamiento.programar_worker_si_corresponde(video.id, usuario)
    return Video.model_validate(video)


@router.delete("/videos/{video_id}/procesar", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[PUEDEN_PROCESAR],
               responses={**_RESPUESTA_404, 409: {"description": "No se está procesando"}},
               summary="CU-27 · Cancelar un procesamiento en curso",
               description="El video vuelve a SUBIDO. El worker se entera en su próximo lote.")
async def cancelar_proceso(video_id: int, usuario: Actual, db: Db) -> None:
    await procesamiento.cancelar(db, usuario, video_id)


@router.post("/trabajos/tomar", response_model=Trabajo,
             dependencies=[PUEDEN_PROCESAR],
             responses={204: {"description": "No hay videos en cola"}},
             summary="T-061 · Worker: tomar el próximo video en cola",
             description=(
                 "Usado por `vision/procesamiento/worker.py`. Devuelve todo lo necesario para "
                 "procesar sin otra consulta: homografía, modelo y colores. Un trabajo sin "
                 "lotes durante 10 minutos se considera abandonado y se puede volver a tomar."
             ))
async def tomar_trabajo(usuario: Actual, db: Db) -> Trabajo | Response:
    trabajo = await procesamiento.tomar(db, usuario)
    return trabajo if trabajo is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/videos/{video_id}/archivo",
            response_class=FileResponse,
            responses={
                **_RESPUESTA_404,
                200: {"content": {"application/octet-stream": {}},
                      "description": "El video; admite `Range` para reanudar la descarga"},
                409: {"description": "El video todavía no terminó de subirse"},
            },
            summary="T-061 · Worker / Visor: descargar o reproducir el video")
async def descargar_video(video_id: int, usuario: Actual, db: Db,
                          almacen: AlmacenDep) -> FileResponse:
    ruta = await procesamiento.archivo(db, usuario, video_id, almacen)
    return FileResponse(ruta, media_type="video/mp4")


@router.post("/partidos/{partido_id}/transmitir-vivo", status_code=status.HTTP_202_ACCEPTED,
             summary="CU-24, CU-40, CU-41 · Iniciar emisión sincronizada a 5 Hz con visor de video/cámara")
async def iniciar_transmision_vivo(partido_id: int, usuario: Actual,
                                   t_inicio_s: float = 0.0,
                                   duracion_s: float = 60.0,
                                   video_id: int | None = None) -> dict[str, object]:
    procesamiento.programar_transmision_vivo_partido(
        partido_id, usuario, duracion_s=duracion_s, t_inicio_s=t_inicio_s, video_id=video_id
    )
    return {
        "ok": True,
        "partido_id": partido_id,
        "video_id": video_id,
        "t_inicio_s": t_inicio_s,
        "duracion_s": duracion_s,
    }


@router.post("/partidos/{partido_id}/pausar-vivo", status_code=status.HTTP_200_OK,
             summary="CU-24, CU-40 · Pausar emisión sincronizada cuando el video o cámara se pausa")
async def pausar_transmision_vivo(partido_id: int, usuario: Actual) -> dict[str, object]:
    await procesamiento.pausar_transmision_vivo_partido(partido_id, usuario.club_id)
    return {"ok": True, "partido_id": partido_id, "estado": "pausado"}


@router.post("/vivo/analizar-cuadro", response_model=MensajeWorker,
             summary="CU-24, CU-40 · Inferencia YOLO + Color en tiempo real desde cámara web o video local")
async def analizar_cuadro_en_vivo(
    archivo: Annotated[UploadFile, File(...)],
    usuario: Actual,
    color_local: Annotated[str, Form()] = "#6CABDD",
    color_rival: Annotated[str, Form()] = "#FFFFFF",
    partido_id: Annotated[int, Form()] = 1,
    t_actual: Annotated[float, Form()] = 0.0,
) -> MensajeWorker:
    contenido = await archivo.read()
    return procesamiento.analizar_fotograma_en_vivo(
        contenido,
        partido_id=partido_id,
        color_local=color_local,
        color_rival=color_rival,
        t_actual=t_actual,
    )


@router.get("/videos/{video_id}/muestras", response_model=list[MensajeWorker],
            summary="CU-24, CU-40, CU-41 · Descargar telemetría persistida del video para sincronización directa")
async def obtener_muestras_video(video_id: int, usuario: Actual, db: Db) -> list[MensajeWorker]:
    vid = await videos.ver_video(db, usuario, video_id)
    muestras = procesamiento.cargar_muestras_video(video_id)
    if not muestras and vid.partido_id:
        muestras = procesamiento.cargar_muestras_partido(vid.partido_id)
    return muestras


@router.post("/videos/{video_id}/resultados", response_model=Video,
             dependencies=[PUEDEN_PROCESAR],
             responses={
                 **_RESPUESTA_404,
                 409: {"description": "Se canceló o ya terminó: el worker debe detenerse"},
             },
             summary="T-061 · Worker: enviar un lote de posiciones y el progreso",
             description=(
                 "Las muestras usan el mismo contrato `MensajeWorker` que la ingesta en vivo y "
                 "se guardan por el mismo camino: un video procesado genera las mismas "
                 "entidades que un partido en vivo."
             ))
async def recibir_resultados(video_id: int, lote: ResultadosLote, usuario: Actual, db: Db,
                             posiciones: PosicionesDep) -> Video:
    video = await procesamiento.recibir_resultados(db, usuario, video_id, lote, posiciones)
    return Video.model_validate(video)


@router.post("/videos/{video_id}/terminar", response_model=Video,
             dependencies=[PUEDEN_PROCESAR],
             responses={**_RESPUESTA_404, 409: {"description": "No se está procesando"}},
             summary="T-061 · Worker: cerrar el procesamiento")
async def terminar_proceso(video_id: int, fin: FinTrabajo, usuario: Actual, db: Db) -> Video:
    return Video.model_validate(await procesamiento.terminar(db, usuario, video_id, fin))
