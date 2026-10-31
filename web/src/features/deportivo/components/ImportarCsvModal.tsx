/**
 * T-043 · CU-12: Vista previa e importación de plantel desde CSV.
 *
 * Flujo de dos fases: al elegir un archivo se pide la vista previa
 * (confirmar=false, nada se guarda); recién al presionar "Confirmar
 * importación" se reenvía el mismo archivo con confirmar=true.
 */
import { useRef, useState } from "react";
import type { ChangeEvent, CSSProperties } from "react";
import type { ResultadoImportacion } from "../types";

interface ImportarCsvModalProps {
  abierto: boolean;
  resultado: ResultadoImportacion | null;
  importado: boolean;
  cargandoPreview: boolean;
  cargandoConfirmar: boolean;
  error: string | null;
  onSeleccionarArchivo: (archivo: File) => void;
  onConfirmar: () => void;
  onCerrar: () => void;
}

export function ImportarCsvModal({
  abierto,
  resultado,
  importado,
  cargandoPreview,
  cargandoConfirmar,
  error,
  onSeleccionarArchivo,
  onConfirmar,
  onCerrar,
}: ImportarCsvModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [nombreArchivo, setNombreArchivo] = useState<string | null>(null);

  if (!abierto) return null;

  const handleArchivo = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    setNombreArchivo(archivo.name);
    onSeleccionarArchivo(archivo);
  };

  const handleCerrar = () => {
    setNombreArchivo(null);
    if (inputRef.current) inputRef.current.value = "";
    onCerrar();
  };

  const cargando = cargandoPreview || cargandoConfirmar;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        backgroundColor: "rgba(0, 0, 0, 0.65)",
        backdropFilter: "blur(3px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !cargando) handleCerrar();
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 10,
          width: "100%",
          maxWidth: 720,
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 40px rgba(0,0,0,0.25)",
          overflow: "hidden",
        }}
      >
        {/* Cabecera */}
        <div
          style={{
            padding: "18px 24px",
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
              CU-12 · Importación de Plantel
            </span>
            <h3 style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 800, color: "var(--text)" }}>
              Importar Jugadores desde CSV
            </h3>
          </div>
          <button
            type="button"
            onClick={handleCerrar}
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

        {/* Cuerpo */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            padding: 24,
            gap: 18,
          }}
        >
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
            El archivo debe tener las columnas obligatorias <code>nombre</code>, <code>apellido</code>,{" "}
            <code>dorsal</code> y <code>altura_cm</code>; opcionalmente <code>posicion</code>,{" "}
            <code>pie_habil</code>, <code>peso_kg</code> y <code>fecha_nacimiento</code>.
          </p>

          {error && (
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
              {error}
            </div>
          )}

          {/* Selector de archivo */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <button
              type="button"
              disabled={cargando}
              onClick={() => inputRef.current?.click()}
              style={{
                all: "unset",
                cursor: cargando ? "wait" : "pointer",
                padding: "9px 16px",
                fontSize: 13,
                fontWeight: 700,
                color: "var(--text)",
                background: "var(--ground)",
                border: "1px solid var(--line)",
                borderRadius: 6,
              }}
            >
              {nombreArchivo ? "Elegir otro archivo…" : "Elegir archivo CSV…"}
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={handleArchivo}
              style={{ display: "none" }}
            />
            {nombreArchivo && (
              <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>{nombreArchivo}</span>
            )}
            {cargandoPreview && (
              <span style={{ fontSize: 12.5, color: "var(--text-3)" }}>Analizando archivo…</span>
            )}
          </div>

          {/* Resultado: vista previa o confirmación */}
          {resultado && (
            <>
              {importado ? (
                <div
                  style={{
                    padding: "14px 16px",
                    borderRadius: 8,
                    background: "var(--ok-bg)",
                    border: "1.5px solid var(--ok)",
                  }}
                >
                  <strong style={{ fontSize: 14, color: "var(--ok)" }}>
                    Importación completada
                  </strong>
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-2)" }}>
                    Se importaron {resultado.importadas} de {resultado.total} filas
                    {resultado.con_error > 0
                      ? ` (${resultado.con_error} con error, no se guardaron).`
                      : "."}
                  </p>
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    gap: 10,
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12.5,
                      fontWeight: 700,
                      color: "var(--text-2)",
                      background: "var(--ground)",
                      border: "1px solid var(--line)",
                      padding: "4px 10px",
                      borderRadius: 5,
                    }}
                  >
                    Total: {resultado.total}
                  </span>
                  <span
                    style={{
                      fontSize: 12.5,
                      fontWeight: 700,
                      color: "var(--ok)",
                      background: "var(--ok-bg)",
                      border: "1px solid var(--ok)",
                      padding: "4px 10px",
                      borderRadius: 5,
                    }}
                  >
                    Válidas: {resultado.importadas}
                  </span>
                  {resultado.con_error > 0 && (
                    <span
                      style={{
                        fontSize: 12.5,
                        fontWeight: 700,
                        color: "var(--risk)",
                        background: "var(--risk-bg)",
                        border: "1px solid var(--risk)",
                        padding: "4px 10px",
                        borderRadius: 5,
                      }}
                    >
                      Con error: {resultado.con_error}
                    </span>
                  )}
                </div>
              )}

              {/* Tabla de detalle fila por fila */}
              <div
                style={{
                  border: "1px solid var(--line)",
                  borderRadius: 8,
                  overflow: "hidden",
                }}
              >
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                  <thead>
                    <tr style={{ background: "var(--ground)" }}>
                      <th style={celdaEncabezado}>Fila</th>
                      <th style={celdaEncabezado}>Nombre</th>
                      <th style={celdaEncabezado}>Apellido</th>
                      <th style={celdaEncabezado}>Dorsal</th>
                      <th style={celdaEncabezado}>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultado.detalle.map((fila) => (
                      <tr
                        key={fila.fila}
                        style={{
                          borderTop: "1px solid var(--line)",
                          background: fila.error ? "var(--risk-bg)" : "transparent",
                        }}
                      >
                        <td style={celdaCuerpo}>{fila.fila}</td>
                        <td style={celdaCuerpo}>{fila.datos.nombre || "—"}</td>
                        <td style={celdaCuerpo}>{fila.datos.apellido || "—"}</td>
                        <td style={celdaCuerpo}>{fila.datos.dorsal || "—"}</td>
                        <td style={{ ...celdaCuerpo, color: fila.error ? "var(--risk)" : "var(--ok)" }}>
                          {fila.error ?? "Válida"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Botones de acción */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 12,
            padding: "16px 24px",
            borderTop: "1px solid var(--line)",
          }}
        >
          <button
            type="button"
            disabled={cargando}
            onClick={handleCerrar}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "9px 18px",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--text-2)",
              background: "var(--ground)",
              borderRadius: 6,
              border: "1px solid var(--line)",
            }}
          >
            {importado ? "Cerrar" : "Cancelar"}
          </button>
          {resultado && !importado && resultado.importadas > 0 && (
            <button
              type="button"
              disabled={cargando}
              onClick={onConfirmar}
              style={{
                all: "unset",
                cursor: cargando ? "wait" : "pointer",
                padding: "9px 22px",
                fontSize: 13,
                fontWeight: 700,
                color: "#ffffff",
                background: "var(--pitch)",
                borderRadius: 6,
                boxShadow: "0 2px 6px rgba(11, 107, 69, 0.25)",
                opacity: cargando ? 0.7 : 1,
              }}
            >
              {cargandoConfirmar
                ? "Importando…"
                : `Confirmar importación (${resultado.importadas})`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const celdaEncabezado: CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  fontSize: 11,
  fontWeight: 700,
  color: "var(--text-3)",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const celdaCuerpo: CSSProperties = {
  padding: "7px 12px",
  color: "var(--text)",
};
