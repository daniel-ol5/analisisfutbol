import { type FormEvent, useState } from "react";

import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Button, Input, Modal, Select } from "@/shared/ui";

import type { Equipo, EquipoCrear } from "../types";
import "./equipo-form.css";

interface EquipoFormModalProps {
  abierto: boolean;
  equipoEditar?: Equipo | null;
  onCerrar: () => void;
  onGuardar: (datos: EquipoCrear & { activo?: boolean }) => Promise<void>;
}

const TEMPORADAS_SUGERIDAS = [
  "2026",
  "2026 - Apertura",
  "2026 - Clausura",
  "2025/2026",
  "2026/2027",
  "Torneo Verano 2026",
  "Copa Nacional 2026",
];

const ESTRUCTURA_FUTBOL: Record<string, Record<string, string[]>> = {
  "Bolivia (FBF)": {
    "División Profesional y Ascenso": [
      "Primera División (División Profesional)",
      "Copa Simón Bolívar (Ascenso Nacional)",
      "Torneo Nacional de Reservas / Promoción",
    ],
    "Asociaciones Departamentales": [
      "Primera A (Asociación Departamental)",
      "Primera B (Asociación Departamental)",
      "Primera de Ascenso",
      "Segunda de Ascenso",
    ],
    "Divisiones Formativas y Juveniles": [
      "Sub-20",
      "Sub-19",
      "Sub-17",
      "Sub-15",
      "Sub-13",
      "Escuelas / Infantil",
    ],
    "Fútbol Femenino": [
      "Liga Femenina de Fútbol Boliviano",
      "Femenino Primera División",
      "Femenino Sub-19",
    ],
  },
  "Argentina (AFA)": {
    "Ligas Profesionales": [
      "Liga Profesional (Primera División)",
      "Primera Nacional (2da División)",
      " Torneo Proyección (Reserva)",
    ],
    "Categorías de Ascenso": ["Primera B Metropolitana", "Torneo Federal A", "Primera C"],
    "Divisiones Inferiores AFA": [
      "Cuarta División (Sub-20)",
      "Quinta División (Sub-18)",
      "Sexta División (Sub-17)",
      "Séptima División (Sub-16)",
      "Octava División (Sub-15)",
      "Novena División (Sub-14)",
    ],
    "Fútbol Femenino": [" Campeonato Femenino YPF (Primera A)", "Primera B Femenina"],
  },
  "España (RFEF / LaLiga)": {
    "Competiciones Nacionales": [
      "Primera División (LaLiga EA Sports)",
      "Segunda División (LaLiga Hypermotion)",
      "Primera Federación (1ª RFEF)",
      "Segunda Federación (2ª RFEF)",
      "Tercera Federación (3ª RFEF)",
    ],
    "Fútbol Base y Juvenil": [
      "Filial / Equipo B",
      "Juvenil División de Honor (U19)",
      "Juvenil Liga Nacional",
      "Cadete División de Honor (U16)",
      "Infantil Autonómico (U14)",
    ],
    "Fútbol Femenino": ["Liga F (Primera División Femenina)", "Primera Federación FutFem"],
  },
  "Brasil (CBF)": {
    "Campeonatos Nacionales": [
      "Brasileirão Série A",
      "Brasileirão Série B",
      "Brasileirão Série C",
      "Brasileirão Série D",
    ],
    "Torneos Estaduales y Base": [
      "Campeonato Estadual (Brasil)",
      "Brasileirão Sub-20",
      "Brasileirão Sub-17",
      "Brasileirão Feminino A1",
    ],
  },
  "Internacional (CONMEBOL / FIFA)": {
    "Torneos Continentales de Clubes": [
      "CONMEBOL Libertadores",
      "CONMEBOL Sudamericana",
      "CONMEBOL Libertadores Sub-20",
      "CONMEBOL Libertadores Femenina",
    ],
    "Selecciones y Torneos Juveniles": [
      "Selección Absoluta",
      "Selección Sub-23 (Preolímpico)",
      "Selección Sub-20",
      "Selección Sub-17",
    ],
  },
};

const PAIS_INICIAL = "Bolivia (FBF)";
const RAMA_INICIAL = "División Profesional y Ascenso";
const TEMPORADA_INICIAL = TEMPORADAS_SUGERIDAS[0];

function ubicarCategoria(categoria?: string) {
  for (const [pais, ramas] of Object.entries(ESTRUCTURA_FUTBOL)) {
    const rama = Object.keys(ramas).find((nombre) =>
      ramas[nombre].some((opcion) => opcion === categoria),
    );
    if (rama) return { pais, rama };
  }
  return null;
}

export function EquipoFormModal({
  abierto,
  equipoEditar,
  onCerrar,
  onGuardar,
}: EquipoFormModalProps) {
  return (
    <Modal
      abierto={abierto}
      titulo={equipoEditar ? "Editar equipo" : "Nuevo equipo"}
      onCerrar={onCerrar}
      className="equipo-modal"
    >
      {abierto && (
        <FormularioEquipo
          key={equipoEditar?.id ?? "nuevo"}
          equipoEditar={equipoEditar}
          onCerrar={onCerrar}
          onGuardar={onGuardar}
        />
      )}
    </Modal>
  );
}

function FormularioEquipo({
  equipoEditar,
  onCerrar,
  onGuardar,
}: Omit<EquipoFormModalProps, "abierto">) {
  const ubicacion = ubicarCategoria(equipoEditar?.categoria);
  const [nombre, setNombre] = useState(equipoEditar?.nombre ?? "");
  const [temporada, setTemporada] = useState(equipoEditar?.temporada || TEMPORADA_INICIAL);
  const [temporadaManual, setTemporadaManual] = useState(!TEMPORADAS_SUGERIDAS.includes(temporada));
  const [pais, setPais] = useState(ubicacion?.pais ?? PAIS_INICIAL);
  const [rama, setRama] = useState(ubicacion?.rama ?? RAMA_INICIAL);
  const [categoria, setCategoria] = useState(
    equipoEditar?.categoria ?? ESTRUCTURA_FUTBOL[PAIS_INICIAL][RAMA_INICIAL][0],
  );
  const [categoriaManual, setCategoriaManual] = useState(Boolean(equipoEditar && !ubicacion));
  const [activo, setActivo] = useState(equipoEditar?.activo ?? true);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ramas = Object.keys(ESTRUCTURA_FUTBOL[pais]);
  const categorias = ESTRUCTURA_FUTBOL[pais][rama];
  const categoriaSugerida = categorias.includes(categoria) ? categoria : categorias[0];
  const temporadaSugerida = TEMPORADAS_SUGERIDAS.includes(temporada)
    ? temporada
    : TEMPORADA_INICIAL;

  const alCambiarPais = (siguiente: string) => {
    const primeraRama = Object.keys(ESTRUCTURA_FUTBOL[siguiente])[0];
    setPais(siguiente);
    setRama(primeraRama);
    setCategoria(ESTRUCTURA_FUTBOL[siguiente][primeraRama][0]);
  };

  const alGuardar = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!nombre.trim()) {
      setError("Escribe el nombre del equipo.");
      return;
    }
    setError(null);
    setEnviando(true);
    try {
      await onGuardar({
        nombre: nombre.trim(),
        temporada: (temporadaManual ? temporada : temporadaSugerida).trim(),
        categoria: (categoriaManual ? categoria : categoriaSugerida).trim(),
        color_local: equipoEditar?.color_local ?? "#1E5AA8",
        color_visitante: equipoEditar?.color_visitante ?? "#FFFFFF",
        color_arquero: equipoEditar?.color_arquero ?? "#F2C200",
        ...(equipoEditar ? { activo } : {}),
      });
      onCerrar();
    } catch (fallo) {
      setError(mensajeDeError(fallo));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form className="equipo-form" onSubmit={alGuardar}>
      <fieldset className="equipo-form-campos" disabled={enviando}>
        {error && <Alert tono="error">{error}</Alert>}
        <div className="equipo-form-grid equipo-form-datos">
          <Input
            etiqueta="Nombre del equipo"
            placeholder="Ej. Horizonte Juvenil"
            required
            maxLength={120}
            value={nombre}
            onChange={(evento) => setNombre(evento.currentTarget.value)}
          />
          <div className="equipo-form-temporada">
            {temporadaManual ? (
              <Input
                etiqueta="Temporada"
                placeholder="Ej. 2027"
                maxLength={20}
                value={temporada}
                onChange={(evento) => setTemporada(evento.currentTarget.value)}
              />
            ) : (
              <Select
                etiqueta="Temporada"
                value={temporadaSugerida}
                title={temporadaSugerida}
                onChange={(evento) => setTemporada(evento.currentTarget.value)}
              >
                {TEMPORADAS_SUGERIDAS.map((opcion) => (
                  <option key={opcion}>{opcion}</option>
                ))}
              </Select>
            )}
            <Button
              className="equipo-form-alternar"
              variante="fantasma"
              onClick={() => setTemporadaManual((manual) => !manual)}
            >
              {temporadaManual ? "Ver temporadas" : "Escribir otra"}
            </Button>
          </div>
        </div>

        <section className="equipo-form-categoria" aria-label="Clasificación del equipo">
          <header>
            <h3>Clasificación</h3>
            <Button
              className="equipo-form-alternar"
              variante="fantasma"
              onClick={() => setCategoriaManual((manual) => !manual)}
              aria-label={categoriaManual ? "Ver categorías" : "Escribir categoría manual"}
            >
              {categoriaManual ? "Ver categorías" : "Escribir categoría"}
            </Button>
          </header>
          {categoriaManual ? (
            <Input
              etiqueta="Categoría"
              placeholder="Ej. Sub-17"
              maxLength={40}
              value={categoria}
              onChange={(evento) => setCategoria(evento.currentTarget.value)}
            />
          ) : (
            <div className="equipo-form-grid">
              <Select
                etiqueta="País o federación"
                value={pais}
                title={pais}
                onChange={(evento) => alCambiarPais(evento.currentTarget.value)}
              >
                {Object.keys(ESTRUCTURA_FUTBOL).map((opcion) => (
                  <option key={opcion}>{opcion}</option>
                ))}
              </Select>
              <Select
                etiqueta="Rama"
                value={rama}
                title={rama}
                onChange={(evento) => {
                  const siguiente = evento.currentTarget.value;
                  setRama(siguiente);
                  setCategoria(ESTRUCTURA_FUTBOL[pais][siguiente][0]);
                }}
              >
                {ramas.map((opcion) => (
                  <option key={opcion}>{opcion}</option>
                ))}
              </Select>
              <div className="equipo-form-division">
                <Select
                  etiqueta="Categoría"
                  value={categoriaSugerida}
                  title={categoriaSugerida}
                  onChange={(evento) => setCategoria(evento.currentTarget.value)}
                >
                  {categorias.map((opcion) => (
                    <option key={opcion}>{opcion}</option>
                  ))}
                </Select>
              </div>
            </div>
          )}
        </section>

        {equipoEditar && (
          <label className="equipo-form-estado">
            <input
              type="checkbox"
              checked={activo}
              onChange={(evento) => setActivo(evento.currentTarget.checked)}
            />
            Equipo activo
          </label>
        )}
      </fieldset>

      <footer className="equipo-form-acciones">
        <Button variante="secundario" onClick={onCerrar} disabled={enviando}>
          Cancelar
        </Button>
        <Button type="submit" disabled={enviando}>
          {enviando ? "Guardando…" : equipoEditar ? "Guardar cambios" : "Crear equipo"}
        </Button>
      </footer>
      <Button
        className="equipo-form-cerrar"
        variante="fantasma"
        aria-label="Cerrar formulario"
        onClick={onCerrar}
        disabled={enviando}
      >
        <span aria-hidden="true">×</span>
      </Button>
    </form>
  );
}
