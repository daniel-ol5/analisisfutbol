import { useState } from "react";

import { ITEMS_ADR, ITEMS_PROPUESTA, type ItemComprobacion } from "../guia";

const TOTAL = ITEMS_ADR.length + ITEMS_PROPUESTA.length;

/** Lista de comprobación previa a calibrar, con contador y aviso final. */
export function ListaComprobacion() {
  const [marcados, setMarcados] = useState<ReadonlySet<string>>(() => new Set<string>());

  function alternar(id: string) {
    setMarcados((previos) => {
      const nuevos = new Set(previos);
      if (nuevos.has(id)) nuevos.delete(id);
      else nuevos.add(id);
      return nuevos;
    });
  }

  function renderItems(items: readonly ItemComprobacion[]) {
    return (
      <ul className="guia-items">
        {items.map((item) => (
          <li key={item.id}>
            <label className="guia-item">
              <input
                type="checkbox"
                checked={marcados.has(item.id)}
                onChange={() => alternar(item.id)}
              />
              <span>{item.texto}</span>
            </label>
          </li>
        ))}
      </ul>
    );
  }

  const completo = marcados.size === TOTAL;

  return (
    <div>
      <p className="guia-contador" aria-live="polite">
        {marcados.size} de {TOTAL} completados
      </p>

      <fieldset className="guia-grupo">
        <legend>Según el ADR-001</legend>
        {renderItems(ITEMS_ADR)}
      </fieldset>

      <fieldset className="guia-grupo">
        <legend>
          Propuestas del equipo <span className="guia-etiqueta">Por confirmar</span>
        </legend>
        {renderItems(ITEMS_PROPUESTA)}
      </fieldset>

      {completo && (
        <p className="guia-listo" role="status">
          Todo está marcado. La cámara está lista para calibrar.
        </p>
      )}
    </div>
  );
}
