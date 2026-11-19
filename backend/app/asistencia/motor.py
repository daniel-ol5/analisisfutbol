"""Evaluación de condiciones y justificaciones sin red ni base de datos."""

import math
import operator
from collections.abc import Mapping
from dataclasses import dataclass
from string import Formatter

from app.asistencia.schemas import DatoSoporte, Prioridad, Regla

_COMPARAR = {
    "<": operator.lt, "<=": operator.le, ">": operator.gt,
    ">=": operator.ge, "==": operator.eq, "!=": operator.ne,
}
_FORMATOS = {"", ".0f", ".1f", ".2f"}


class ReglaInvalida(ValueError):
    """Una regla fuera del formato soportado no debe interrumpir el partido."""


class MetricaNoDisponible(ValueError):
    """La observación no alcanza para evaluar la regla de forma fiable."""


@dataclass(frozen=True, slots=True)
class Disparo:
    mensaje: str
    justificacion: str
    datos_soporte: list[DatoSoporte]


def _numero(valor: object) -> float:
    if type(valor) not in (int, float):
        raise ReglaInvalida("Se esperaba un valor numérico")
    try:
        numero = float(valor)
    except OverflowError as e:
        raise ReglaInvalida("Valor numérico fuera de rango") from e
    if not math.isfinite(numero):
        raise ReglaInvalida("Se esperaba un número finito")
    return numero


def evaluar_condicion(condicion: dict, metricas: Mapping[str, float]) -> tuple[bool, list[DatoSoporte]]:
    """Evalúa comparaciones y grupos `y`/`o`. Todas sus métricas deben estar disponibles."""
    campos: dict[tuple[str, float], DatoSoporte] = {}
    nodos = 0

    def resolver(operando: object) -> float:
        if isinstance(operando, str):
            if not operando.isidentifier():
                raise ReglaInvalida("Identificador de métrica inválido")
            if operando not in metricas:
                raise MetricaNoDisponible(operando)
            try:
                return _numero(metricas[operando])
            except ReglaInvalida as e:
                raise MetricaNoDisponible(operando) from e
        return _numero(operando)

    def visitar(expresion: object, profundidad: int) -> bool:
        nonlocal nodos
        nodos += 1
        if profundidad > 8 or nodos > 64 or not isinstance(expresion, dict) or len(expresion) != 1:
            raise ReglaInvalida("Expresión inválida o demasiado anidada")
        op, args = next(iter(expresion.items()))
        if not isinstance(args, list) or not args or len(args) > 64:
            raise ReglaInvalida("El operador requiere una lista de argumentos")
        if op in ("y", "o"):
            resultados = [visitar(arg, profundidad + 1) for arg in args]
            return all(resultados) if op == "y" else any(resultados)
        if op not in _COMPARAR or len(args) != 2 or not any(isinstance(a, str) for a in args):
            raise ReglaInvalida(f"Comparación no soportada: {op}")
        izq, der = map(resolver, args)
        for nombre, valor, umbral in ((args[0], izq, der), (args[1], der, izq)):
            if isinstance(nombre, str):
                campos[nombre, umbral] = DatoSoporte(metrica=nombre, valor=valor, umbral=umbral)
        return _COMPARAR[op](izq, der)

    cumple = visitar(condicion, 0)
    return cumple, list(campos.values()) if cumple else []


def _renderizar(plantilla: str, metricas: Mapping[str, float]) -> str:
    partes: list[str] = []
    try:
        for texto, campo, formato, conversion in Formatter().parse(plantilla):
            partes.append(texto)
            if campo is None:
                continue
            if conversion or formato not in _FORMATOS or not campo.isidentifier():
                raise ReglaInvalida("Campo de plantilla inválido")
            if campo not in metricas:
                raise MetricaNoDisponible(campo)
            partes.append(format(_numero(metricas[campo]), formato))
    except (ReglaInvalida, MetricaNoDisponible):
        raise
    except ValueError as e:
        raise ReglaInvalida("Plantilla inválida") from e
    return "".join(partes)


def evaluar_regla(regla: Regla, metricas: Mapping[str, float]) -> Disparo | None:
    if not regla.activa:
        return None
    try:
        cumple, datos = evaluar_condicion(regla.condicion, metricas)
        if cumple:
            return Disparo(
                _renderizar(regla.plantilla_mensaje, metricas),
                _renderizar(regla.plantilla_justificacion, metricas),
                datos,
            )
    except MetricaNoDisponible:
        return None
    return None


ORDEN_PRIORIDAD = {prioridad: orden for orden, prioridad in enumerate(Prioridad)}

# CU-54: lo único que una regla puede consultar. Son las métricas que produce
# `contexto.EstadoTactico.metricas()`, las de disciplina de `service._disciplina`
# y el minuto. Una regla con un nombre mal escrito nunca se dispararía y nadie
# se enteraría, así que al crearla o editarla se rechaza.
METRICAS_DISPONIBLES = frozenset({
    "minuto",
    "altura_linea_m", "amplitud_propia_m", "compacidad_propia_m",
    "posesion_propia_pct", "posesion_rival_pct",
    "pases_intentados_propios", "pases_completados_rival", "precision_pase_propio_pct",
    "ritmo_propio_m_min", "caida_ritmo_propio_pct",
    "amarillas_propias_10min", "rojas_propias",
})


class _Sonda(Mapping[str, float]):
    """Responde a cualquier métrica y anota cuáles se pidieron."""

    def __init__(self) -> None:
        self.pedidas: set[str] = set()

    def __contains__(self, clave: object) -> bool:
        return isinstance(clave, str)

    def __getitem__(self, clave: str) -> float:
        self.pedidas.add(clave)
        return 1.0

    def __iter__(self):
        return iter(self.pedidas)

    def __len__(self) -> int:
        return len(self.pedidas)


def validar_regla(condicion: dict, plantilla_mensaje: str, plantilla_justificacion: str) -> None:
    """Rechaza (ReglaInvalida) una regla que el motor no podría evaluar nunca.

    Recorre la condición completa (`y`/`o` evalúan todos sus argumentos) y las dos
    plantillas con una sonda, así reporta todas las métricas desconocidas juntas.
    """
    sonda = _Sonda()
    evaluar_condicion(condicion, sonda)
    _renderizar(plantilla_mensaje, sonda)
    _renderizar(plantilla_justificacion, sonda)
    desconocidas = sorted(sonda.pedidas - METRICAS_DISPONIBLES)
    if desconocidas:
        raise ReglaInvalida(
            f"Métricas desconocidas: {', '.join(desconocidas)}. "
            f"Disponibles: {', '.join(sorted(METRICAS_DISPONIBLES))}"
        )
