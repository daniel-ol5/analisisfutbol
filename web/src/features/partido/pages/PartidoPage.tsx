/** Operación del Partido  —  P4 · CU-30 … CU-39 */
import { Pendiente } from "@/shared/ui/Pendiente";

const CASOS = [
  "CU-30 Iniciar y finalizar partido",
  "CU-31 Dirección de ataque",
  "CU-32 Capturar partido en vivo",
  "CU-33 Sincronizar captura",
  "CU-34 Asignar jugadores a identificadores",
  "CU-35 Reasignar identificador",
  "CU-36 Registrar gol",
  "CU-37 Registrar tarjeta",
  "CU-38 Registrar sustitución",
  "CU-39 Supervisar calidad",
];

export function PartidoPage() {
  return <Pendiente paquete="P4" titulo="Operación del Partido" casos={CASOS} />;
}
