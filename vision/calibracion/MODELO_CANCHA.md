# Checkpoint de cancha

Origen: [ejemplo oficial de Roboflow Sports](https://github.com/roboflow/sports/blob/main/examples/soccer/setup.sh),
archivo `football-pitch-detection.pt`, publicado como descarga del propio ejemplo.

- Tarea: pose de una cancha, 32 referencias; no pose humana.
- Tamaño descargado: 140212306 bytes.
- SHA256: `28f68f7c4056d6d9b137efd2e7ab5f3c494039380c63831649126ced25628b36`.
- Instalación: desde `vision`, `python -m calibracion.instalar_modelo`.
- Fuente de etiquetas: [configuración del ejemplo](https://github.com/roboflow/sports/blob/main/sports/configs/soccer.py).
- Atribución y condiciones del proyecto de origen:
  [README de Roboflow Sports](https://github.com/roboflow/sports/tree/main/examples/soccer).

Las medidas del ejemplo no se copian como dimensiones reales de nuestra cancha.
Se usan las dimensiones configuradas y las medidas de las marcas; Y se convierte
a la convención de la aplicación. Los extremos de la elipse central se excluyen
del ajuste porque no son referencias proyectivas fijas.

La confianza del modelo no valida la calibración. Se comprueban distribución de
hitos, correspondencias robustas y alineación con líneas visibles. El modelo
puede no funcionar en un encuadre: se informa pérdida de referencia.
