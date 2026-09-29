/** Análisis Táctico  —  P5 · CU-40 … CU-48 */
import { Pendiente } from "@/shared/ui/Pendiente";

const CASOS = [
  "CU-40 Panel del partido en vivo",
  "CU-41 Plano 2D de posiciones",
  "CU-42 Posesión y circulación",
  "CU-43 Métricas físicas por jugador",
  "CU-44 Mapas de calor",
  "CU-45 Métricas tácticas colectivas",
  "CU-46 Evolución por intervalos",
  "CU-47 Línea de tiempo",
  "CU-48 Red de pases",
];

export function AnalisisPage() {
  return <Pendiente paquete="P5" titulo="Análisis Táctico" casos={CASOS} />;
}
