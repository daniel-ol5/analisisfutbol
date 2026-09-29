/** Gestión Deportiva  —  P2 · CU-09 … CU-17 */
import { Pendiente } from "@/shared/ui/Pendiente";

const CASOS = [
  "CU-09 Gestionar equipos",
  "CU-10 Indumentaria del equipo",
  "CU-11 Gestionar jugadores",
  "CU-12 Importar plantel",
  "CU-13 Gestionar competiciones",
  "CU-14 Programar partido",
  "CU-15 Agenda de partidos",
  "CU-16 Reprogramar o cancelar",
  "CU-17 Alineación y formación",
];

export function DeportivoPage() {
  return <Pendiente paquete="P2" titulo="Gestión Deportiva" casos={CASOS} />;
}
