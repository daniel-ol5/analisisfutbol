import { Link, Navigate, Route, Routes, useNavigate, useSearchParams } from "react-router-dom";

import { useSesion } from "@/features/seguridad";
import { Pestanas } from "@/shared/ui/Pestanas";

import { AlineacionView } from "../components/AlineacionView";
import { EquiposView } from "../components/EquiposView";
import { IndumentariaView } from "../components/IndumentariaView";
import { JugadoresView } from "../components/JugadoresView";
import { PartidosView } from "../components/PartidosView";

const EQUIPOS = "/deportivo/equipos";
const INDUMENTARIA = "/deportivo/equipos/indumentaria";
const CALENDARIO = "/deportivo/calendario";
const ALINEACION = "/deportivo/calendario/alineacion";

function idSeleccionado(valor: string | null) {
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

export function DeportivoPage() {
  const navegar = useNavigate();
  const [parametros] = useSearchParams();
  const equipoId = idSeleccionado(parametros.get("equipo"));
  const partidoId = idSeleccionado(parametros.get("partido"));
  const rol = useSesion()?.usuario.rol;
  const puedeProgramar = rol === "ADMIN" || rol === "DT";
  const pestanas = [
    { ruta: EQUIPOS, titulo: "Equipos" },
    { ruta: "/deportivo/plantel", titulo: "Plantel" },
    { ruta: CALENDARIO, titulo: "Calendario" },
    ...(puedeProgramar ? [{ ruta: "/deportivo/competiciones", titulo: "Competiciones" }] : []),
  ];

  return (
    <main className="area-pagina">
      <header className="area-titulo">
        <h1>Gestión deportiva</h1>
      </header>
      <Pestanas titulo="Gestión deportiva" enlaces={pestanas} />
      <div className="area-contenido">
        <Routes>
          <Route index element={<Navigate to={EQUIPOS} replace />} />
          <Route
            path="equipos"
            element={
              <>
                <div className="area-subvista">
                  <h2>Equipos del club</h2>
                  <Link to={INDUMENTARIA}>Indumentaria →</Link>
                </div>
                <EquiposView
                  onIrIndumentaria={(id) =>
                    navegar(id ? `${INDUMENTARIA}?equipo=${id}` : INDUMENTARIA)
                  }
                />
              </>
            }
          />
          <Route
            path="equipos/indumentaria"
            element={
              <>
                <div className="area-subvista">
                  <h2>Indumentaria</h2>
                  <Link to={EQUIPOS}>← Volver a equipos</Link>
                </div>
                <IndumentariaView equipoInicialId={equipoId} />
              </>
            }
          />
          <Route
            path="plantel"
            element={<JugadoresView key={equipoId} equipoInicialId={equipoId} />}
          />
          <Route
            path="calendario"
            element={
              <PartidosView onVerAlineacion={(id) => navegar(`${ALINEACION}?partido=${id}`)} />
            }
          />
          <Route
            path="calendario/programar"
            element={
              puedeProgramar ? (
                <PartidosView key="programar" vista="programar" />
              ) : (
                <Navigate to={CALENDARIO} replace />
              )
            }
          />
          <Route
            path="calendario/alineacion"
            element={
              <>
                <div className="area-subvista">
                  <h2>Alineación</h2>
                  <Link to={CALENDARIO}>← Volver al calendario</Link>
                </div>
                <AlineacionView key={partidoId ?? "sin"} partidoInicialId={partidoId} />
              </>
            }
          />
          <Route
            path="competiciones"
            element={
              puedeProgramar ? (
                <PartidosView key="competiciones" vista="competiciones" />
              ) : (
                <Navigate to={CALENDARIO} replace />
              )
            }
          />
          <Route path="*" element={<Navigate to={EQUIPOS} replace />} />
        </Routes>
      </div>
    </main>
  );
}
