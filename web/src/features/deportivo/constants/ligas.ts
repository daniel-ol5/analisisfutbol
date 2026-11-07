export interface PaisLiga {
  id: string;
  nombre: string;
  bandera: string;
  divisiones: string[];
}

export const PAISES_Y_LIGAS: PaisLiga[] = [
  {
    id: "bo",
    nombre: "Bolivia",
    bandera: "🇧🇴",
    divisiones: [
      "División Profesional (Liga Tecno)",
      "Copa Bolivia",
      "Copa Simón Bolívar",
      "Torneo de Reservas (Sub-20)",
      "Juvenil Sub-19",
      "Juvenil Sub-17",
      "Juvenil Sub-15",
      "Liga Femenina Profesional",
    ],
  },
  {
    id: "es",
    nombre: "España",
    bandera: "🇪🇸",
    divisiones: [
      "LaLiga EA Sports (1ª División)",
      "LaLiga Hypermotion (2ª División)",
      "Primera Federación (1ª RFEF)",
      "División de Honor Juvenil",
      "Filiales / Equipo B",
      "Liga Femenina (Liga F)",
    ],
  },
  {
    id: "de",
    nombre: "Alemania",
    bandera: "🇩🇪",
    divisiones: [
      "Bundesliga",
      "2. Bundesliga",
      "3. Liga",
      "DFB-Nachwuchsliga (U19)",
      "DFB-Nachwuchsliga (U17)",
      "Frauen-Bundesliga",
    ],
  },
  {
    id: "ar",
    nombre: "Argentina",
    bandera: "🇦🇷",
    divisiones: [
      "Liga Profesional de Fútbol (Primera)",
      "Primera Nacional",
      "Torneo Proyección (Reserva)",
      "Juveniles AFA (Sub-20 a Sub-15)",
      "Primera División Femenina",
    ],
  },
  {
    id: "br",
    nombre: "Brasil",
    bandera: "🇧🇷",
    divisiones: [
      "Brasileirão Série A",
      "Brasileirão Série B",
      "Copa do Brasil",
      "Brasileirão Sub-20",
      "Brasileirão Feminino",
    ],
  },
  {
    id: "intl",
    nombre: "Internacional / Copas",
    bandera: "🌐",
    divisiones: [
      "CONMEBOL Libertadores",
      "CONMEBOL Sudamericana",
      "UEFA Champions League",
      "Torneo Amistoso Internacional",
    ],
  },
  {
    id: "custom",
    nombre: "Personalizada / Club Emergente",
    bandera: "⚙️",
    divisiones: ["Personalizada (Escribir nombre...)"],
  },
];

export const TEMPORADAS_SUGERIDAS = [
  "2026",
  "2026/2027",
  "2025/2026",
  "2025",
  "Apertura 2026",
  "Clausura 2026",
];
