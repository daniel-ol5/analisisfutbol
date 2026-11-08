"""Procesamiento diferido de video grabado  —  CU-27 (T-061).

`worker.py` toma trabajos del backend; `mensajes.py` une las piezas del
pipeline en un `MensajeWorker`; `fuente.py` corre YOLO + ByteTrack sobre el
video; `api.py` habla con el backend. Solo `fuente.py` (y el modo real de
`worker.py`) necesitan ultralytics, y lo importan recién al usarse.
"""
