"""Compatibilidad: los modelos falsos de partido y posición ya no existen.

Las pruebas usan las tablas reales (`partido` de T-047 y `posicion` de T-033)
desde tests/partidos_prueba.py. Este módulo solo reexporta el motor sin pool,
porque otras pruebas lo importan desde aquí (test_partido_control.py y
test_partido_tracks.py).
"""

from partidos_prueba import SesionesPrueba, motor

__all__ = ["SesionesPrueba", "motor"]
