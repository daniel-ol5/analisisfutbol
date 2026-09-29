/** Visión por Computadora  —  P3 · CU-18 … CU-29 */
import { Pendiente } from "@/shared/ui/Pendiente";

const CASOS = [
  "CU-18 Guía de montaje de cámara",
  "CU-19 Calibrar cámara",
  "CU-20 Medidas de la cancha",
  "CU-21 Validar error de calibración",
  "CU-22 Reutilizar calibración",
  "CU-23 Corregir distorsión",
  "CU-27 Procesar video grabado",
  "CU-28 Cargar video",
  "CU-29 Versiones del modelo",
];

export function VisionPage() {
  return <Pendiente paquete="P3" titulo="Visión por Computadora" casos={CASOS} />;
}
