/** Asistencia y Reportes  —  P6 · CU-49 … CU-58 */
import { Pendiente } from "@/shared/ui/Pendiente";

const CASOS = [
  "CU-49 Evaluar reglas tácticas",
  "CU-50 Recibir recomendación",
  "CU-51 Valorar recomendación",
  "CU-52 Alerta de estado de jugador",
  "CU-53 Notificación push",
  "CU-54 Catálogo de reglas",
  "CU-55 Informe post-partido",
  "CU-56 Exportar métricas",
  "CU-57 Comparar con la temporada",
  "CU-58 Clips de jugadas",
];

export function AsistenciaPage() {
  return <Pendiente paquete="P6" titulo="Asistencia y Reportes" casos={CASOS} />;
}
