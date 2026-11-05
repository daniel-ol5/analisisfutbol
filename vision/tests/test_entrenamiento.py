import yaml

from deteccion.modelo import CLASES_PROPIO
from entrenamiento.entrenar import DATASET_YAML
from seguimiento.tipos import Clase


def test_dataset_yaml_coincide_con_clases_propio():
    """`dataset.yaml::names` y `CLASES_PROPIO` deben tener los mismos indices.

    Si se desincronizan, el modelo entrenado etiqueta una clase con el
    nombre de otra (ej. jugador donde deberia decir arbitro) sin que nada
    lo detecte hasta ver el resultado en cancha.
    """
    con_dataset = yaml.safe_load(DATASET_YAML.read_text(encoding="utf-8"))
    nombres_dataset = con_dataset["names"]

    nombres_esperados = {indice: clase.value.lower() for indice, clase in CLASES_PROPIO.items()}

    assert nombres_dataset == nombres_esperados


def test_clases_propio_incluye_arbitro():
    """El punto de HU-20/CU-29: a diferencia de `CLASES_COCO`, el modelo
    propio distingue arbitro como clase de deteccion, no solo por color."""
    assert Clase.ARBITRO in CLASES_PROPIO.values()
