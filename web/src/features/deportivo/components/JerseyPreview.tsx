interface JerseyPreviewProps {
  color: string;
  size?: "sm" | "md" | "lg";
  etiqueta?: string;
  className?: string;
}

export function JerseyPreview({
  color,
  size = "md",
  etiqueta,
  className = "",
}: JerseyPreviewProps) {
  // Dimensiones según tamaño
  const dims = {
    sm: { w: 32, h: 32, font: 9 },
    md: { w: 52, h: 52, font: 11 },
    lg: { w: 84, h: 84, font: 13 },
  }[size];

  // Cálculo de contraste para el ribete y número según luminosidad del color
  const hex = color.trim().replace(/^#/, "");
  let esColorClaro = false;
  if (/^[0-9A-Fa-f]{6}$/.test(hex)) {
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    // Fórmula de luminancia relativa
    const luma = 0.299 * r + 0.587 * g + 0.114 * b;
    esColorClaro = luma > 180;
  }

  const trimColor = esColorClaro ? "#1a2520" : "#ffffff";
  const trimOpacity = esColorClaro ? 0.35 : 0.45;

  return (
    <div
      className={`jersey-container ${className}`}
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
      }}
    >
      <svg
        width={dims.w}
        height={dims.h}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          filter: "drop-shadow(0 3px 6px rgba(0,0,0,0.18))",
          transition: "transform 0.15s ease",
        }}
      >
        <defs>
          <linearGradient id={`grad-${color}-${size}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.88" />
          </linearGradient>
          <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#000" stopOpacity="0.12" />
            <stop offset="15%" stopColor="#fff" stopOpacity="0.08" />
            <stop offset="85%" stopColor="#fff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#000" stopOpacity="0.12" />
          </linearGradient>
        </defs>

        {/* Silueta de Camiseta de Fútbol */}
        <path
          d="M34 16 L22 28 L6 20 L2 38 L16 46 L16 88 C16 91 19 93 22 93 L78 93 C81 93 84 91 84 88 L84 46 L98 38 L94 20 L78 28 L66 16 C63 24 37 24 34 16 Z"
          fill={`url(#grad-${color}-${size})`}
          stroke="rgba(0,0,0,0.22)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* Capa de textura y brillo */}
        <path
          d="M34 16 L22 28 L6 20 L2 38 L16 46 L16 88 C16 91 19 93 22 93 L78 93 C81 93 84 91 84 88 L84 46 L98 38 L94 20 L78 28 L66 16 C63 24 37 24 34 16 Z"
          fill="url(#shade)"
        />

        {/* Cuello redondo / V */}
        <path
          d="M34 16 C38 25 62 25 66 16"
          stroke={trimColor}
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeOpacity={trimOpacity}
        />

        {/* Ribete en mangas */}
        <path
          d="M2 38 L16 46"
          stroke={trimColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeOpacity={trimOpacity}
        />
        <path
          d="M98 38 L84 46"
          stroke={trimColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeOpacity={trimOpacity}
        />

        {/* Línea sutil en hombros */}
        <path
          d="M34 16 L22 28"
          stroke={trimColor}
          strokeWidth="1.5"
          strokeOpacity={trimOpacity * 0.7}
        />
        <path
          d="M66 16 L78 28"
          stroke={trimColor}
          strokeWidth="1.5"
          strokeOpacity={trimOpacity * 0.7}
        />

        {/* Escudo o número central para realismo */}
        {size !== "sm" && (
          <circle
            cx="32"
            cy="36"
            r="4.5"
            fill={trimColor}
            fillOpacity={trimOpacity}
          />
        )}
      </svg>

      {etiqueta && (
        <span
          style={{
            fontSize: dims.font,
            fontWeight: 600,
            color: "var(--text-2)",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          {etiqueta}
        </span>
      )}
    </div>
  );
}
