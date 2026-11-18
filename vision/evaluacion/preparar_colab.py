"""Empaqueta solo código del worker para subirlo a un cuaderno de Colab."""
import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


def preparar(salida: Path) -> dict[str, str]:
    vision = Path(__file__).resolve().parents[1]
    paquetes = ("calibracion", "deteccion", "evaluacion", "procesamiento", "seguimiento")
    rutas = [r for paquete in paquetes for r in (vision / paquete).rglob("*")
             if r.is_file() and r.suffix in {".py", ".yaml"} and "__pycache__" not in r.parts]
    rutas.extend(vision / nombre for nombre in ("requirements.txt", "requirements-pruebas.txt", "README.md"))
    manifiesto = {r.relative_to(vision).as_posix(): hashlib.sha256(r.read_bytes()).hexdigest()
                 for r in sorted(rutas)}
    salida.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(salida, "x", compression=zipfile.ZIP_DEFLATED) as paquete:
        for ruta in sorted(rutas):
            paquete.write(ruta, f"vision/{ruta.relative_to(vision).as_posix()}")
        paquete.writestr("manifiesto.json", json.dumps(manifiesto, indent=2))
    return manifiesto


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, default=Path(tempfile.gettempdir()) / "analisisfutbol-colab.zip")
    args = p.parse_args()
    manifiesto = preparar(args.salida)
    print(f"{args.salida.resolve()} ({len(manifiesto)} archivos; sin videos, pesos ni credenciales)")


if __name__ == "__main__":
    main()
