/** Seguridad y Administración  —  P1 · CU-01 … CU-08 */
import { Pendiente } from "@/shared/ui/Pendiente";

const CASOS = [
  "CU-01 Registrar club",
  "CU-02 Iniciar sesión",
  "CU-03 Cerrar sesión",
  "CU-04 Gestionar usuarios y roles",
  "CU-05 Administrar perfil propio",
  "CU-06 Recuperar contraseña",
  "CU-07 Bitácora de auditoría",
  "CU-08 Resumen de actividad del club",
];

export function SeguridadPage() {
  return <Pendiente paquete="P1" titulo="Seguridad y Administración" casos={CASOS} />;
}
