import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listarEquipos,
  crearEquipo,
  editarEquipo,
  desactivarEquipo,
  conectarSesionDemo,
  tieneSesion,
} from "../api";
import { EquipoCard } from "./EquipoCard";
import { EquipoFormModal } from "./EquipoFormModal";
import { ColorVerificationModal } from "./ColorVerificationModal";
import { calcularDistanciaHsv } from "../types";
import type { Equipo, EquipoCrear, EquipoEditar } from "../types";

export function EquiposView() {
  const queryClient = useQueryClient();
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [categoriaFiltro, setCategoriaFiltro] = useState<string>("todas");

  // Estados de modales
  const [modalFormAbierto, setModalFormAbierto] = useState(false);
  const [equipoAEditar, setEquipoAEditar] = useState<Equipo | null>(null);

  const [modalRivalAbierto, setModalRivalAbierto] = useState(false);
  const [equipoParaRival, setEquipoParaRival] = useState<Equipo | null>(null);

  const [sesionConectada, setSesionConectada] = useState(tieneSesion());
  const [conectandoDemo, setConectandoDemo] = useState(false);

  // Consulta de equipos
  const {
    data: equipos = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["equipos", { activos: !mostrarInactivos }],
    queryFn: () => listarEquipos(!mostrarInactivos),
    enabled: sesionConectada,
    retry: 1,
  });

  // Mutación crear
  const mutationCrear = useMutation({
    mutationFn: (datos: EquipoCrear) => crearEquipo(datos),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
      setModalFormAbierto(false);
    },
  });

  // Mutación editar
  const mutationEditar = useMutation({
    mutationFn: ({ id, datos }: { id: number; datos: EquipoEditar }) =>
      editarEquipo(id, datos),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
      setModalFormAbierto(false);
      setEquipoAEditar(null);
    },
  });

  // Mutación desactivar (baja lógica)
  const mutationDesactivar = useMutation({
    mutationFn: (id: number) => desactivarEquipo(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
    },
  });

  // Conectar sesión demo rápida si no hay token
  const handleConectarDemo = async () => {
    try {
      setConectandoDemo(true);
      await conectarSesionDemo();
      setSesionConectada(true);
      await refetch();
    } catch (err) {
      console.error("Error al iniciar sesión demo:", err);
    } finally {
      setConectandoDemo(false);
    }
  };

  // Detección de pares de equipos con colores demasiado similares en el club (Criterio T-041)
  const colisionesClub = useMemo(() => {
    const colisiones: Array<{
      equipo1: Equipo;
      equipo2: Equipo;
      distancia: number;
    }> = [];

    const activos = equipos.filter((e) => e.activo);
    for (let i = 0; i < activos.length; i++) {
      for (let j = i + 1; j < activos.length; j++) {
        const e1 = activos[i];
        const e2 = activos[j];
        const dist = calcularDistanciaHsv(e1.color_local, e2.color_local);
        if (dist !== null && dist < 40) {
          colisiones.push({
            equipo1: e1,
            equipo2: e2,
            distancia: dist,
          });
        }
      }
    }
    return colisiones;
  }, [equipos]);

  // Mapa de IDs de equipos en conflicto para resaltado rápido
  const mapaConflictos = useMemo(() => {
    const mapa = new Map<number, string>();
    for (const c of colisionesClub) {
      mapa.set(c.equipo1.id, c.equipo2.nombre);
      mapa.set(c.equipo2.id, c.equipo1.nombre);
    }
    return mapa;
  }, [colisionesClub]);

  // Categorías únicas para filtro
  const categorias = useMemo(() => {
    const set = new Set<string>();
    equipos.forEach((e) => {
      if (e.categoria) set.add(e.categoria);
    });
    return Array.from(set);
  }, [equipos]);

  // Filtro de búsqueda y categoría
  const equiposFiltrados = useMemo(() => {
    return equipos.filter((e) => {
      const coincideBusqueda =
        e.nombre.toLowerCase().includes(busqueda.toLowerCase()) ||
        e.temporada.toLowerCase().includes(busqueda.toLowerCase()) ||
        e.categoria.toLowerCase().includes(busqueda.toLowerCase());

      const coincideCategoria =
        categoriaFiltro === "todas" || e.categoria === categoriaFiltro;

      return coincideBusqueda && coincideCategoria;
    });
  }, [equipos, busqueda, categoriaFiltro]);

  const totalJugadores = useMemo(() => {
    return equipos.reduce((acc, eq) => acc + (eq.jugadores || 0), 0);
  }, [equipos]);

  const handleGuardarForm = async (datos: EquipoCrear | EquipoEditar) => {
    if (equipoAEditar) {
      await mutationEditar.mutateAsync({ id: equipoAEditar.id, datos });
    } else {
      await mutationCrear.mutateAsync(datos as EquipoCrear);
    }
  };

  const handleDesactivar = async (equipo: Equipo) => {
    const seguro = window.confirm(
      `¿Estás seguro de desactivar el equipo "${equipo.nombre}"?\n` +
      `Se mantendrán todos los registros históricos de partidos y jugadores asociados.`
    );
    if (seguro) {
      await mutationDesactivar.mutateAsync(equipo.id);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Banner de autenticación / conexión demo si no hay sesión o si la API dio 401 */}
      {(!sesionConectada || isError) && (
        <div
          style={{
            padding: "16px 20px",
            background: "rgba(11, 107, 69, 0.08)",
            border: "1.5px solid var(--pitch)",
            borderRadius: 8,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <div>
              <strong style={{ fontSize: 14, color: "var(--pitch)" }}>
                Conexión con el Club · Módulo de Gestión Deportiva
              </strong>
              <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--text-2)" }}>
                Para consultar y administrar los equipos del club se requiere una sesión activa con token JWT.
              </p>
            </div>
            <button
              type="button"
              disabled={conectandoDemo}
              onClick={handleConectarDemo}
              style={{
                all: "unset",
                cursor: conectandoDemo ? "wait" : "pointer",
                padding: "8px 18px",
                fontSize: 13,
                fontWeight: 700,
                color: "#ffffff",
                background: "var(--pitch)",
                borderRadius: 6,
                boxShadow: "0 2px 6px rgba(11, 107, 69, 0.25)",
              }}
            >
              {conectandoDemo ? "Conectando…" : "⚡ Conectar Sesión Demo (Club Bolívar)"}
            </button>
          </div>
          {isError && (
            <p style={{ margin: 0, fontSize: 11.5, color: "var(--risk)" }}>
              {(error as any)?.response?.data?.detail ??
                "Error de autorización: Haga clic en el botón superior para autenticarse automáticamente."}
            </p>
          )}
        </div>
      )}

      {/* Alerta Global de Colisión de Indumentaria en el Club (Criterio de Aceptación T-041) */}
      {colisionesClub.length > 0 && (
        <div
          style={{
            padding: "16px 20px",
            borderRadius: 8,
            background: "rgba(162, 55, 42, 0.08)",
            border: "1.5px solid var(--risk)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 20 }}>⚠️</span>
            <div>
              <h4 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: "var(--risk)" }}>
                Advertencia de Similitud de Colores en el Club (T-041)
              </h4>
              <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--text-2)" }}>
                Se detectaron equipos activos con indumentaria titular demasiado próxima en espacio HSV (distancia &lt; 40).
              </p>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {colisionesClub.map(({ equipo1, equipo2, distancia }) => (
              <div
                key={`${equipo1.id}-${equipo2.id}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  background: "var(--surface)",
                  borderRadius: 6,
                  border: "1px solid var(--line)",
                  fontSize: 12.5,
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 3,
                      backgroundColor: equipo1.color_local,
                      border: "1px solid rgba(0,0,0,0.2)",
                    }}
                  />
                  <strong>{equipo1.nombre}</strong> ({equipo1.color_local})
                  <span style={{ color: "var(--text-3)", fontWeight: 700 }}>↔</span>
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 3,
                      backgroundColor: equipo2.color_local,
                      border: "1px solid rgba(0,0,0,0.2)",
                    }}
                  />
                  <strong>{equipo2.nombre}</strong> ({equipo2.color_local})
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontWeight: 700,
                      color: "var(--risk)",
                      background: "rgba(162, 55, 42, 0.1)",
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontSize: 11,
                    }}
                  >
                    Distancia HSV: {distancia.toFixed(1)} &lt; 40
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setEquipoAEditar(equipo2);
                      setModalFormAbierto(true);
                    }}
                    style={{
                      all: "unset",
                      cursor: "pointer",
                      fontSize: 11.5,
                      fontWeight: 600,
                      color: "var(--pitch)",
                      textDecoration: "underline",
                    }}
                  >
                    Editar color de {equipo2.nombre}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Métricas y resumen superior */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
        }}
      >
        <div
          style={{
            padding: "14px 18px",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 6,
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-3)" }}>
            Equipos Activos
          </span>
          <p style={{ margin: "4px 0 0", fontSize: 24, fontWeight: 800, color: "var(--text)" }}>
            {equipos.filter((e) => e.activo).length}
          </p>
        </div>

        <div
          style={{
            padding: "14px 18px",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 6,
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-3)" }}>
            Total Jugadores
          </span>
          <p style={{ margin: "4px 0 0", fontSize: 24, fontWeight: 800, color: "var(--text)" }}>
            {totalJugadores}
          </p>
        </div>

        <div
          style={{
            padding: "14px 18px",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 6,
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--text-3)" }}>
            Estado de Contraste Óptico
          </span>
          <p
            style={{
              margin: "4px 0 0",
              fontSize: 15,
              fontWeight: 800,
              color: colisionesClub.length > 0 ? "var(--risk)" : "var(--pitch)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {colisionesClub.length > 0 ? (
              <>⚠️ {colisionesClub.length} advertencia(s)</>
            ) : (
              <>✓ Óptimo para Visión</>
            )}
          </p>
        </div>
      </div>

      {/* Barra de herramientas: Búsqueda, Filtros y Botón Nuevo Equipo */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          padding: 16,
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", flex: 1 }}>
          <input
            type="text"
            placeholder="Buscar por nombre, categoría o temporada…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            style={{
              minWidth: 260,
              flex: 1,
              padding: "8px 12px",
              fontSize: 13,
              borderRadius: 6,
              border: "1px solid var(--line)",
              background: "var(--ground)",
              color: "var(--text)",
              outline: "none",
            }}
          />

          {categorias.length > 0 && (
            <select
              value={categoriaFiltro}
              onChange={(e) => setCategoriaFiltro(e.target.value)}
              style={{
                padding: "8px 12px",
                fontSize: 13,
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "var(--ground)",
                color: "var(--text)",
                outline: "none",
              }}
            >
              <option value="todas">Todas las Categorías</option>
              {categorias.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          )}

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12.5,
              color: "var(--text-2)",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Ver inactivos
          </label>
        </div>

        <button
          type="button"
          onClick={() => {
            setEquipoAEditar(null);
            setModalFormAbierto(true);
          }}
          style={{
            all: "unset",
            cursor: "pointer",
            padding: "9px 18px",
            fontSize: 13,
            fontWeight: 700,
            color: "#ffffff",
            background: "var(--pitch)",
            borderRadius: 6,
            boxShadow: "0 2px 6px rgba(11, 107, 69, 0.25)",
            whiteSpace: "nowrap",
          }}
        >
          + Registrar Nuevo Equipo
        </button>
      </div>

      {/* Grid de Equipos */}
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-3)", fontSize: 14 }}>
          Cargando equipos del club…
        </div>
      ) : equiposFiltrados.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 48,
            background: "var(--surface)",
            border: "1px dashed var(--line)",
            borderRadius: 8,
          }}
        >
          <span style={{ fontSize: 36, display: "block", marginBottom: 8 }}>🛡️</span>
          <h4 style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>
            {busqueda || categoriaFiltro !== "todas"
              ? "No se encontraron equipos que coincidan con la búsqueda."
              : "Aún no hay equipos registrados en el club."}
          </h4>
          <p style={{ margin: "6px 0 16px", fontSize: 13, color: "var(--text-2)" }}>
            Comienza registrando tu primer plantel con su juego de indumentarias titular, visitante y arquero.
          </p>
          <button
            type="button"
            onClick={() => {
              setEquipoAEditar(null);
              setModalFormAbierto(true);
            }}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "8px 18px",
              fontSize: 13,
              fontWeight: 700,
              color: "#ffffff",
              background: "var(--pitch)",
              borderRadius: 6,
            }}
          >
            + Registrar Primer Equipo
          </button>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))",
            gap: 16,
          }}
        >
          {equiposFiltrados.map((equipo) => (
            <EquipoCard
              key={equipo.id}
              equipo={equipo}
              tieneConflictoConOtro={mapaConflictos.has(equipo.id)}
              otroEquipoEnConflicto={mapaConflictos.get(equipo.id)}
              onEditar={(eq) => {
                setEquipoAEditar(eq);
                setModalFormAbierto(true);
              }}
              onVerificarRival={(eq) => {
                setEquipoParaRival(eq);
                setModalRivalAbierto(true);
              }}
              onDesactivar={handleDesactivar}
            />
          ))}
        </div>
      )}

      {/* Modal de Alta / Edición con selector de 3 colores y detección de colisión */}
      <EquipoFormModal
        abierto={modalFormAbierto}
        equipoAEditar={equipoAEditar}
        otrosEquipos={equipos}
        cargando={mutationCrear.isPending || mutationEditar.isPending}
        onCerrar={() => {
          setModalFormAbierto(false);
          setEquipoAEditar(null);
        }}
        onGuardar={handleGuardarForm}
      />

      {/* Modal de Verificación de Contraste vs Rival */}
      <ColorVerificationModal
        abierto={modalRivalAbierto}
        equipo={equipoParaRival}
        otrosEquipos={equipos}
        onCerrar={() => {
          setModalRivalAbierto(false);
          setEquipoParaRival(null);
        }}
      />
    </div>
  );
}
