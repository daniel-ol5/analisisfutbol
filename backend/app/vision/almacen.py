"""Almacén de videos de partido  —  T-060 (CU-28).

Los endpoints solo conocen la interfaz `AlmacenVideos`. Hoy la implementa
`AlmacenEnDisco`, que escribe en una carpeta (en Docker, un volumen).

>>> PUNTO ÚNICO DE CONEXIÓN CON EL ALMACENAMIENTO DE OBJETOS <<<
⚠️ PROVISORIO: el README pide almacenamiento de objetos para los videos. Cuando
exista (S3 o MinIO), agregar un `AlmacenS3` con la misma interfaz (subida
multiparte y `ruta_local` que descarga a un temporal) y devolverlo en
`obtener_almacen_videos`. Los endpoints y el contrato no cambian.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class TrozoDemasiadoGrande(Exception):
    """El cuerpo trajo más bytes de los que declaró el Content-Range."""


class AlmacenVideos(Protocol):
    def clave(self, club_id: int, video_id: int, extension: str) -> str:
        """Dónde se guarda el video; es lo que va en `video.archivo_url`."""
        ...

    async def escribir(
        self, clave: str, desde: int, trozos: AsyncIterator[bytes], maximo: int
    ) -> int:
        """Escribe a partir del byte `desde` y devuelve cuántos bytes escribió.

        Escribe en la posición, no al final: si un trozo se reenvía (red
        cortada antes de la respuesta), lo pisa en vez de duplicarlo.
        Lanza `TrozoDemasiadoGrande` si llegan más de `maximo` bytes.
        """
        ...

    def ruta_local(self, clave: str) -> Path:
        """Archivo en disco para leerlo con OpenCV."""
        ...

    async def borrar(self, clave: str) -> None: ...


class AlmacenEnDisco:
    def __init__(self, raiz: str | Path) -> None:
        self.raiz = Path(raiz)

    def clave(self, club_id: int, video_id: int, extension: str) -> str:
        # Una carpeta por club: el aislamiento (Pb-03) también en disco.
        return f"club-{club_id}/video-{video_id}{extension}"

    def ruta_local(self, clave: str) -> Path:
        ruta = (self.raiz / clave).resolve()
        if not ruta.is_relative_to(self.raiz.resolve()):
            raise ValueError("Clave fuera del almacén")
        return ruta

    async def escribir(
        self, clave: str, desde: int, trozos: AsyncIterator[bytes], maximo: int
    ) -> int:
        ruta = self.ruta_local(clave)
        await asyncio.to_thread(ruta.parent.mkdir, parents=True, exist_ok=True)
        # r+b no trunca; si es el primer trozo el archivo todavía no existe.
        modo = "r+b" if ruta.exists() else "wb"
        archivo = await asyncio.to_thread(open, ruta, modo)
        escritos = 0
        try:
            await asyncio.to_thread(archivo.seek, desde)
            async for pedazo in trozos:
                escritos += len(pedazo)
                if escritos > maximo:
                    raise TrozoDemasiadoGrande
                await asyncio.to_thread(archivo.write, pedazo)
        finally:
            await asyncio.to_thread(archivo.close)
        return escritos

    async def borrar(self, clave: str) -> None:
        await asyncio.to_thread(self.ruta_local(clave).unlink, True)


def obtener_almacen_videos() -> AlmacenVideos:
    """Dependencia de FastAPI; las pruebas la reemplazan por una carpeta temporal."""
    return AlmacenEnDisco(settings.videos_dir)
