"""Descarga verificable del checkpoint público de cancha usado en el ensayo."""
import hashlib
import urllib.request
from pathlib import Path

URL = "https://drive.usercontent.google.com/download?id=1Ma5Kt86tgpdjCTKfum79YMgNnSjcoOyf&export=download&confirm=t"
SHA256 = "28f68f7c4056d6d9b137efd2e7ab5f3c494039380c63831649126ced25628b36"
DESTINO = Path(__file__).resolve().parents[1] / "pesos" / "yolo_cancha_keypoints.pt"


def instalar(destino: Path = DESTINO) -> Path:
    if destino.exists():
        if hashlib.sha256(destino.read_bytes()).hexdigest() != SHA256:
            raise ValueError("Ya existe otro checkpoint en el destino; no se sobrescribe")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".descarga")
    try:
        with urllib.request.urlopen(URL, timeout=60) as entrada, temporal.open("xb") as salida:
            while bloque := entrada.read(1024 * 1024):
                salida.write(bloque)
        if hashlib.sha256(temporal.read_bytes()).hexdigest() != SHA256:
            raise ValueError("La descarga no coincide con el checkpoint evaluado")
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    return destino


if __name__ == "__main__":
    print(instalar())
