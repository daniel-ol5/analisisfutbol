"""Exporta el esquema OpenAPI a docs/api/openapi.json.

Ese archivo es el contrato congelado del Sprint 1: de el salen los mocks que
usan Web y Movil para trabajar sin esperar al backend.

    python scripts/exportar_openapi.py

Correr despues de cualquier cambio en un router o un schema, y commitear el
resultado junto al cambio. La integracion continua verifica que este al dia.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.main import app  # noqa: E402

SALIDA = RAIZ / "docs" / "api" / "openapi.json"


def main() -> None:
    esquema = app.openapi()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(esquema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ops = sum(1 for p in esquema["paths"].values() for _ in p)
    print(f"{SALIDA.relative_to(RAIZ)}")
    print(f"  {len(esquema['paths'])} rutas · {ops} operaciones · "
          f"{len(esquema['components']['schemas'])} esquemas")


if __name__ == "__main__":
    main()
