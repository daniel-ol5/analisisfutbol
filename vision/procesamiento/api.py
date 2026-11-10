"""Cliente del backend para el worker de procesamiento  —  CU-27 (T-061).

Solo biblioteca estándar: el worker no suma dependencias a vision/requirements.
Contrato en `backend/app/vision/router.py` (sección T-061).

Procesar un partido lleva más que los 15 minutos que dura el token de acceso:
ante un 401 se vuelve a iniciar sesión y se repite el pedido una vez.
"""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

Abrir = Callable[..., Any]


class Cancelado(Exception):
    """El backend respondió 409 a un lote: alguien canceló el procesamiento."""


class ErrorApi(Exception):
    def __init__(self, codigo: int, detalle: str) -> None:
        super().__init__(f"{codigo}: {detalle}")
        self.codigo = codigo
        self.detalle = detalle


class ApiBackend:
    def __init__(self, base: str, email: str = "", password: str = "",
                 abrir: Abrir = urllib.request.urlopen, timeout: float = 60,
                 token: str | None = None) -> None:
        self.base = base.rstrip("/")
        self.email = email
        self.password = password
        self._abrir = abrir
        self.timeout = timeout
        self._token: str | None = token

    # ---------- HTTP ----------

    def _pedido(self, metodo: str, ruta: str, cuerpo: Any = None,
                encabezados: dict[str, str] | None = None) -> urllib.request.Request:
        url = ruta if ruta.startswith("http") else f"{self.base}{ruta.removeprefix('/api')}"
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        pedido = urllib.request.Request(url, data=datos, method=metodo)
        pedido.add_header("Content-Type", "application/json")
        if self._token:
            pedido.add_header("Authorization", f"Bearer {self._token}")
        for nombre, valor in (encabezados or {}).items():
            pedido.add_header(nombre, valor)
        return pedido

    def _llamar(self, metodo: str, ruta: str, cuerpo: Any = None, autenticar: bool = True,
                encabezados: dict[str, str] | None = None) -> Any:
        """Devuelve la respuesta abierta. Reintenta una vez con sesión nueva ante un 401."""
        if autenticar and self._token is None:
            self.iniciar_sesion()
        for intento in (1, 2):
            try:
                return self._abrir(self._pedido(metodo, ruta, cuerpo, encabezados),
                                   timeout=self.timeout)
            except urllib.error.HTTPError as e:
                if e.code == 401 and autenticar and intento == 1:
                    self.iniciar_sesion()
                    continue
                raise ErrorApi(e.code, _detalle(e)) from None
        raise AssertionError("inalcanzable")

    def _json(self, metodo: str, ruta: str, cuerpo: Any = None, **kw: Any) -> Any:
        with self._llamar(metodo, ruta, cuerpo, **kw) as respuesta:
            crudo = respuesta.read()
            return json.loads(crudo) if crudo else None

    # ---------- Contrato ----------

    def iniciar_sesion(self) -> None:
        if not self.email or not self.password:
            if self._token:
                raise ErrorApi(401, "Token de acceso expirado y sin credenciales para renovar")
            raise ErrorApi(401, "Faltan credenciales de acceso para iniciar sesión")
        self._token = None
        datos = self._json("POST", "/seguridad/login",
                           {"email": self.email, "password": self.password}, autenticar=False)
        self._token = datos["access_token"]

    def tomar(self) -> dict[str, Any] | None:
        """El próximo trabajo del club, o None si no hay (204)."""
        with self._llamar("POST", "/vision/trabajos/tomar") as respuesta:
            if respuesta.status == 204:
                return None
            return json.loads(respuesta.read())

    def descargar(self, ruta: str, destino: Path, intentos: int = 3) -> Path:
        """Baja el video a `destino`; si se corta, sigue desde donde quedó (Range)."""
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.unlink(missing_ok=True)
        for intento in range(1, intentos + 1):
            desde = destino.stat().st_size if destino.exists() else 0
            rango = {"Range": f"bytes={desde}-"} if desde else None
            try:
                with self._llamar("GET", ruta, encabezados=rango) as respuesta, \
                        open(destino, "ab") as archivo:
                    shutil.copyfileobj(respuesta, archivo, length=1024 * 1024)
                return destino
            except OSError:  # incluye URLError: red caída a mitad de la descarga
                if intento == intentos:
                    raise
        return destino

    def resultados(self, video_id: int, progreso_pct: int, muestras: list[dict[str, Any]]) -> None:
        try:
            self._json("POST", f"/vision/videos/{video_id}/resultados",
                       {"progreso_pct": progreso_pct, "muestras": muestras})
        except ErrorApi as e:
            if e.codigo == 409:
                raise Cancelado(e.detalle) from None
            raise

    # ---------- Modelos (CU-29, usados por evaluacion/regresion.py) ----------

    def modelo_activo(self) -> dict[str, Any] | None:
        modelos = self._json("GET", "/vision/modelos")
        return next((m for m in modelos if m.get("activo")), None)

    def registrar_modelo(self, datos: dict[str, Any]) -> dict[str, Any]:
        """Registra la versión con sus métricas. Nunca la activa: eso es un paso aparte."""
        return self._json("POST", "/vision/modelos", datos)

    def terminar(self, video_id: int, ok: bool, mensaje_error: str | None = None) -> None:
        try:
            self._json("POST", f"/vision/videos/{video_id}/terminar",
                       {"ok": ok, "mensaje_error": mensaje_error})
        except ErrorApi as e:
            if e.codigo != 409:  # 409: lo cancelaron justo al final; no hay nada que cerrar
                raise


def _detalle(error: urllib.error.HTTPError) -> str:
    try:
        cuerpo = json.loads(error.read() or b"{}")
    except ValueError:
        return error.reason
    detalle = cuerpo.get("detail") if isinstance(cuerpo, dict) else None
    return detalle if isinstance(detalle, str) else json.dumps(detalle or cuerpo)
