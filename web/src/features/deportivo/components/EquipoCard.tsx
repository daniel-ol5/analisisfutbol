import { Link } from "react-router-dom";

import { Badge, Button } from "@/shared/ui";

import type { Equipo } from "../types";
import "./equipo-card.css";

interface EquipoCardProps {
  equipo: Equipo;
  onVer: (equipo: Equipo) => void;
  onEditar: (equipo: Equipo) => void;
  onDesactivar: (equipo: Equipo) => void;
  onReactivar?: (equipo: Equipo) => void;
  onIrIndumentaria?: (equipo: Equipo) => void;
}

export function EquipoCard({
  equipo,
  onVer,
  onEditar,
  onDesactivar,
  onReactivar,
  onIrIndumentaria,
}: EquipoCardProps) {
  const jugadores = `${equipo.jugadores} ${equipo.jugadores === 1 ? "jugador" : "jugadores"}`;

  return (
    <article className="equipo-card">
      <header className="equipo-card-cabecera">
        <div>
          <h3>
            <button type="button" onClick={() => onVer(equipo)}>
              {equipo.nombre}
            </button>
          </h3>
          <p>
            {[equipo.categoria, equipo.temporada].filter(Boolean).join(" · ") ||
              "Sin categoría ni temporada"}
          </p>
        </div>
        {!equipo.activo && <Badge>Inactivo</Badge>}
      </header>
      <div className="equipo-card-accesos">
        {equipo.activo ? (
          <Link
            to={`/deportivo/plantel?equipo=${equipo.id}`}
            aria-label={`Plantel de ${equipo.nombre}`}
          >
            {jugadores} →
          </Link>
        ) : (
          <span>{jugadores}</span>
        )}
        {onIrIndumentaria && (
          <button
            type="button"
            onClick={() => onIrIndumentaria(equipo)}
            aria-label={`Indumentaria de ${equipo.nombre}`}
          >
            <span className="equipo-card-colores" aria-hidden="true">
              {[equipo.color_local, equipo.color_visitante, equipo.color_arquero].map(
                (color, indice) => (
                  <i key={indice} style={{ backgroundColor: color }} />
                ),
              )}
            </span>
            Indumentaria
          </button>
        )}
      </div>
      <footer className="equipo-card-acciones">
        <Button variante="secundario" onClick={() => onEditar(equipo)}>
          Editar
        </Button>
        {equipo.activo ? (
          <Button variante="fantasma" onClick={() => onDesactivar(equipo)}>
            Dar de baja
          </Button>
        ) : (
          onReactivar && (
            <Button variante="secundario" onClick={() => onReactivar(equipo)}>
              Reactivar
            </Button>
          )
        )}
      </footer>
    </article>
  );
}
