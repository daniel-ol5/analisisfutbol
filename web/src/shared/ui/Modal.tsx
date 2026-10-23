import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  abierto: boolean;
  titulo: string;
  onCerrar: () => void;
  children: ReactNode;
  /** Botones de acción, alineados abajo a la derecha. */
  acciones?: ReactNode;
}

/**
 * Diálogo modal sobre <dialog>: el navegador atrapa el foco, cierra con Esc
 * y devuelve el foco al elemento que lo abrió.
 */
export function Modal({ abierto, titulo, onCerrar, children, acciones }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const idTitulo = useId();

  useEffect(() => {
    const dialogo = ref.current;
    if (!dialogo) return;
    if (abierto && !dialogo.open) dialogo.showModal();
    if (!abierto && dialogo.open) dialogo.close();
  }, [abierto]);

  return (
    <dialog
      ref={ref}
      className="ui-modal"
      aria-labelledby={idTitulo}
      onClose={onCerrar}
      onClick={(evento) => {
        // Clic en el fondo (el propio <dialog>), no en su contenido.
        if (evento.target === ref.current) onCerrar();
      }}
    >
      <div className="ui-modal-cuerpo">
        <h2 id={idTitulo} className="ui-modal-titulo">
          {titulo}
        </h2>
        {children}
        {acciones && <div className="ui-modal-acciones">{acciones}</div>}
      </div>
    </dialog>
  );
}
