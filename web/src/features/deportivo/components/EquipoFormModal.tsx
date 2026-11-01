import { useState } from "react";
import type { FormEvent } from "react";
import { ColorPickerKit } from "./ColorPickerKit";
import { PAISES_Y_LIGAS, TEMPORADAS_SUGERIDAS } from "../constants/ligas";
import type { Equipo, EquipoCrear, EquipoEditar } from "../types";

interface EquipoFormModalProps {
  abierto: boolean;
  equipoAEditar?: Equipo | null;
  otrosEquipos: Equipo[];
  cargando?: boolean;
  onCerrar: () => void;
  onGuardar: (datos: EquipoCrear | EquipoEditar) => Promise<void>;
}

export function EquipoFormModal({
  abierto,
  equipoAEditar,
  cargando = false,
  onCerrar,
  onGuardar,
}: EquipoFormModalProps) {
  const [nombre, setNombre] = useState(equipoAEditar?.nombre ?? "");
  const [temporada, setTemporada] = useState(equipoAEditar?.temporada ?? "2026");
  const [colorLocal, setColorLocal] = useState(equipoAEditar?.color_local ?? "#1E5AA8");
  const [colorVisitante, setColorVisitante] = useState(equipoAEditar?.color_visitante ?? "#FFFFFF");
  const [colorArquero, setColorArquero] = useState(equipoAEditar?.color_arquero ?? "#F2C200");
  const [errorLocal, setErrorLocal] = useState<string | null>(null);

  // Inicialización de país y división derivada
  const inicial = (() => {
    if (!equipoAEditar?.categoria) {
      return { pais: "bo", div: "División Profesional (Liga Tecno)", custom: false, customVal: "" };
    }
    for (const p of PAISES_Y_LIGAS) {
      if (p.divisiones.includes(equipoAEditar.categoria)) {
        return { pais: p.id, div: equipoAEditar.categoria, custom: false, customVal: "" };
      }
    }
    return { pais: "custom", div: "", custom: true, customVal: equipoAEditar.categoria };
  })();

  const [paisId, setPaisId] = useState<string>(inicial.pais);
  const [divisionSeleccionada, setDivisionSeleccionada] = useState<string>(inicial.div);
  const [categoriaPersonalizada, setCategoriaPersonalizada] = useState<string>(inicial.customVal);
  const [esCategoriaPersonalizada, setEsCategoriaPersonalizada] = useState<boolean>(inicial.custom);

  if (!abierto) return null;

  const paisActual = PAISES_Y_LIGAS.find((p) => p.id === paisId) ?? PAISES_Y_LIGAS[0];

  const handleCambioPais = (nuevoPaisId: string) => {
    setPaisId(nuevoPaisId);
    const p = PAISES_Y_LIGAS.find((item) => item.id === nuevoPaisId);
    if (nuevoPaisId === "custom") {
      setEsCategoriaPersonalizada(true);
    } else if (p && p.divisiones.length > 0) {
      setDivisionSeleccionada(p.divisiones[0]);
      setEsCategoriaPersonalizada(false);
    }
  };

  const handleCambioDivision = (valor: string) => {
    if (valor === "__otra__") {
      setEsCategoriaPersonalizada(true);
    } else {
      setEsCategoriaPersonalizada(false);
      setDivisionSeleccionada(valor);
    }
  };

  const categoriaFinal = esCategoriaPersonalizada
    ? categoriaPersonalizada.trim() || "Personalizada"
    : divisionSeleccionada;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!nombre.trim()) {
      setErrorLocal("El nombre del equipo es obligatorio.");
      return;
    }

    if (!categoriaFinal.trim()) {
      setErrorLocal("Debes especificar la categoría o liga del equipo.");
      return;
    }

    const regexHex = /^#[0-9A-Fa-f]{6}$/;
    if (!regexHex.test(colorLocal) || !regexHex.test(colorVisitante) || !regexHex.test(colorArquero)) {
      setErrorLocal("Los colores deben tener formato hexadecimal válido (#RRGGBB).");
      return;
    }

    setErrorLocal(null);
    try {
      await onGuardar({
        nombre: nombre.trim(),
        categoria: categoriaFinal,
        temporada: temporada.trim() || "2026",
        color_local: colorLocal,
        color_visitante: colorVisitante,
        color_arquero: colorArquero,
      });
      onCerrar();
    } catch (err: any) {
      setErrorLocal(err?.response?.data?.detail ?? "Error al guardar el equipo.");
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        backdropFilter: "blur(3px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !cargando) onCerrar();
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 10,
          width: "100%",
          maxWidth: 700,
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 40px rgba(0,0,0,0.3)",
          overflow: "hidden",
        }}
      >
        {/* Cabecera del modal */}
        <div
          style={{
            padding: "16px 22px",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "var(--pitch)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              CU-09 &amp; CU-10 · Gestión de Equipos e Indumentaria
            </span>
            <h3 style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 800, color: "var(--text)" }}>
              {equipoAEditar ? `Editar Equipo: ${equipoAEditar.nombre}` : "Registrar Nuevo Equipo"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            disabled={cargando}
            style={{
              all: "unset",
              cursor: "pointer",
              fontSize: 20,
              lineHeight: 1,
              color: "var(--text-3)",
              padding: "4px 8px",
              borderRadius: 4,
            }}
          >
            ✕
          </button>
        </div>

        {/* Formulario con scroll vertical */}
        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            padding: 22,
            gap: 20,
          }}
        >
          {errorLocal && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 6,
                background: "rgba(224, 112, 92, 0.12)",
                border: "1px solid var(--risk)",
                color: "var(--risk)",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {errorLocal}
            </div>
          )}

          {/* Nombre del equipo */}
          <div>
            <label
              style={{
                display: "block",
                fontSize: 12,
                fontWeight: 700,
                color: "var(--text)",
                marginBottom: 6,
              }}
            >
              Nombre del Equipo / Plantel *
            </label>
            <input
              type="text"
              required
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="ej. Primera División, Reserva Sub-20, Filial B, Femenino"
              style={{
                width: "100%",
                padding: "9px 12px",
                fontSize: 14,
                color: "var(--text)",
                background: "var(--ground)",
                border: "1px solid var(--line)",
                borderRadius: 6,
                outline: "none",
              }}
            />
          </div>

          {/* Selector de Liga, División y Temporada */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              padding: 14,
              background: "var(--ground)",
              border: "1px solid var(--line)",
              borderRadius: 8,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>
                Liga, División o Competición
              </label>
              <span style={{ fontSize: 11, color: "var(--text-3)" }}>
                Preconfiguradas + Personalizadas
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1.6fr 1fr", gap: 10 }}>
              {/* País / Ámbito */}
              <div>
                <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-3)", marginBottom: 4 }}>
                  País / Ámbito
                </label>
                <select
                  value={paisId}
                  onChange={(e) => handleCambioPais(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    fontSize: 13,
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    outline: "none",
                  }}
                >
                  {PAISES_Y_LIGAS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.bandera} {p.nombre}
                    </option>
                  ))}
                </select>
              </div>

              {/* División o Torneo */}
              <div>
                <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-3)", marginBottom: 4 }}>
                  División / Torneo
                </label>
                {paisId === "custom" || esCategoriaPersonalizada ? (
                  <input
                    type="text"
                    value={categoriaPersonalizada}
                    onChange={(e) => setCategoriaPersonalizada(e.target.value)}
                    placeholder="Escribe el nombre de la liga o categoría…"
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      fontSize: 13,
                      borderRadius: 6,
                      border: "1.5px solid var(--pitch)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      outline: "none",
                    }}
                  />
                ) : (
                  <select
                    value={divisionSeleccionada}
                    onChange={(e) => handleCambioDivision(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      fontSize: 13,
                      borderRadius: 6,
                      border: "1px solid var(--line)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      outline: "none",
                    }}
                  >
                    {paisActual.divisiones.map((div) => (
                      <option key={div} value={div}>
                        {div}
                      </option>
                    ))}
                    <option value="__otra__">✏️ Otra categoría (personalizada)…</option>
                  </select>
                )}
              </div>

              {/* Temporada */}
              <div>
                <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "var(--text-3)", marginBottom: 4 }}>
                  Temporada
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    type="text"
                    list="temporadas-list"
                    value={temporada}
                    onChange={(e) => setTemporada(e.target.value)}
                    placeholder="2026"
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      fontSize: 13,
                      borderRadius: 6,
                      border: "1px solid var(--line)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      outline: "none",
                    }}
                  />
                  <datalist id="temporadas-list">
                    {TEMPORADAS_SUGERIDAS.map((t) => (
                      <option key={t} value={t} />
                    ))}
                  </datalist>
                </div>
              </div>
            </div>

            {esCategoriaPersonalizada && paisId !== "custom" && (
              <button
                type="button"
                onClick={() => setEsCategoriaPersonalizada(false)}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  fontSize: 11.5,
                  color: "var(--pitch)",
                  fontWeight: 600,
                  textDecoration: "underline",
                  alignSelf: "flex-start",
                }}
              >
                ← Volver a divisiones predefinidas de {paisActual.nombre}
              </button>
            )}
          </div>

          {/* Nota informativa de colores institucionales */}
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 6,
              background: "rgba(11, 107, 69, 0.08)",
              border: "1px solid rgba(11, 107, 69, 0.25)",
              fontSize: 12,
              color: "var(--text-2)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span>🛡️</span>
            <span>
              <strong>Identidad del Club:</strong> Todos los planteles pueden compartir los colores
              institucionales. Las advertencias de contraste óptico se evaluarán contra los equipos rivales
              al disputar cada partido.
            </span>
          </div>

          {/* Selector visual de indumentaria con paleta ampliada y hex */}
          <div>
            <label
              style={{
                display: "block",
                fontSize: 13,
                fontWeight: 700,
                color: "var(--text)",
                marginBottom: 8,
              }}
            >
              Colores de Indumentaria (CU-10)
            </label>
            <ColorPickerKit
              colorLocal={colorLocal}
              colorVisitante={colorVisitante}
              colorArquero={colorArquero}
              onChangeLocal={setColorLocal}
              onChangeVisitante={setColorVisitante}
              onChangeArquero={setColorArquero}
            />
          </div>

          {/* Botones de acción */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: 12,
              paddingTop: 16,
              borderTop: "1px solid var(--line)",
            }}
          >
            <button
              type="button"
              onClick={onCerrar}
              disabled={cargando}
              style={{
                all: "unset",
                cursor: "pointer",
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: 600,
                color: "var(--text-2)",
                background: "var(--ground)",
                border: "1px solid var(--line)",
                borderRadius: 6,
              }}
            >
              Cancelar
            </button>

            <button
              type="submit"
              disabled={cargando}
              style={{
                all: "unset",
                cursor: cargando ? "not-allowed" : "pointer",
                padding: "8px 20px",
                fontSize: 13,
                fontWeight: 700,
                color: "#ffffff",
                background: "var(--pitch)",
                borderRadius: 6,
                boxShadow: "0 2px 6px rgba(11, 107, 69, 0.25)",
                opacity: cargando ? 0.7 : 1,
              }}
            >
              {cargando ? "Guardando…" : equipoAEditar ? "Guardar Cambios" : "Registrar Equipo"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
