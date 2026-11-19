import { Link } from "react-router-dom";

import { useSesion } from "@/features/seguridad";

import { Icono } from "@/shared/ui/Icono";

import { MODULOS } from "./navegacion";
import { puedeAcceder } from "./permisos";

export function Inicio() {
  const rol = useSesion()?.usuario.rol;
  const modulos = MODULOS.filter((modulo) => puedeAcceder(rol, modulo.ruta));

  return (
    <main className="area-pagina inicio">
      <header className="area-titulo">
        <h1>Panel del club</h1>
      </header>
      {puedeAcceder(rol, "/partido") && (
        <section className="inicio-destacado" aria-labelledby="Inicio-partido">
          <div className="inicio-destacado-texto">
            <h2 id="Inicio-partido">Día de partido</h2>
            <p>Gestiona el reloj, los eventos y el seguimiento desde el control en vivo.</p>
            <Link to="/partido">
              Abrir control de partido <Icono nombre="flecha" />
            </Link>
          </div>
          <div className="inicio-cancha" aria-hidden="true">
            <div className="inicio-cancha-lineas">
              <i />
              <i />
            </div>
          </div>
        </section>
      )}
      <section aria-labelledby="Inicio-modulos">
        <h2 id="Inicio-modulos" className="inicio-seccion">
          Módulos
        </h2>
        <div className="inicio-modulos">
          {modulos.map((modulo) => (
            <Link to={modulo.ruta} key={modulo.ruta} className="inicio-modulo">
              <span className="inicio-modulo-icono">
                <Icono nombre={modulo.icono} />
              </span>
              <span className="inicio-modulo-texto">
                <strong>{modulo.nombre}</strong>
                <span>{modulo.descripcion}</span>
              </span>
              <Icono nombre="flecha" />
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
