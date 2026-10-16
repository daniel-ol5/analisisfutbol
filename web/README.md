# Área Técnica — Aplicación Web

Frontend web del sistema de análisis táctico de fútbol por visión computacional. Desarrollado con **React 19**, **TypeScript** (modo estricto) y **Vite 8**.

---

## Instalación y Arranque

### Requisitos previos

- Node.js 22 LTS
- npm

### Pasos para iniciar el entorno local

```bash
# 1. Instalar dependencias
npm install

# 2. Configurar variables de entorno locales
copy .env.example .env.local

# 3. Iniciar servidor de desarrollo
npm run dev
```

La aplicación quedará disponible en [http://localhost:5173](http://localhost:5173).

---

## Tabla de Scripts

| Script              | Comando                | Descripción                                                                                 |
| ------------------- | ---------------------- | ------------------------------------------------------------------------------------------- |
| `npm run dev`       | `vite`                 | Inicia el servidor de desarrollo local con HMR en el puerto 5173.                           |
| `npm run build`     | `tsc -b && vite build` | Compila TypeScript con referencias de proyecto y genera el bundle de producción en `dist/`. |
| `npm run preview`   | `vite preview`         | Previsualiza localmente el build de producción generado.                                    |
| `npm run lint`      | `oxlint`               | Analiza el código fuente con Oxlint aplicando reglas de React y TypeScript.                 |
| `npm run format`    | `prettier --write .`   | Formatea el código fuente y archivos de configuración con Prettier.                         |
| `npm run typecheck` | `tsc -b`               | Ejecuta la verificación estricta de tipos de TypeScript sin emitir archivos.                |

---

## Variables de Entorno

La aplicación centraliza la lectura y validación de variables de entorno en `@/shared/config/env.ts`.

> [!IMPORTANT]
> **Regla de oro:** Ningún componente ni archivo debe acceder directamente a `import.meta.env`. Toda lectura debe importarse desde `@/shared/config/env`. Si falta una variable requerida, la aplicación arrojará un error descriptivo inmediato al inicio.

### Variables disponibles

- `VITE_API_URL`: URL base de la API.
  - Para el backend real: `http://127.0.0.1:8000/api`
  - Para el mock server (Prism): `http://127.0.0.1:4010/api`
- `VITE_USE_MOCKS`: `"true"` o `"false"`. Permite activar flags de datos simulados mientras los casos de uso retornen `501`.

Los valores locales van en `.env.local`, el cual está ignorado en Git para evitar filtrar secretos o configuraciones personales.

---

## Alias de Importación (`@/`)

Está configurado el alias `@/` apuntando a `src/`:

- **Vite:** Configurado en `vite.config.ts` mediante `fileURLToPath(new URL('./src', import.meta.url))`.
- **TypeScript:** Configurado en `tsconfig.app.json` en `"paths": { "@/*": ["./src/*"] }` sin `baseUrl` (práctica recomendada y compatible con TypeScript 6).

### Convención de importación

Siempre utiliza el alias `@/` en lugar de rutas relativas largas:

```ts
// Correcto
import { api } from "@/shared/api/client";
import { env } from "@/shared/config/env";

// Incorrecto
import { api } from "../../../shared/api/client";
```

---

## Estructura del Proyecto

El proyecto sigue una arquitectura modular dividida por **features** (coherente con el backend y la app móvil) y un espacio **shared** para recursos comunes.

```
web/
├── public/                 # Archivos estáticos servidos directamente
├── src/
│   ├── app/                # Configuración global, providers y enrutador principal
│   │   ├── Inicio.tsx      # Dashboard inicial con verificación de salud del backend
│   │   ├── providers.tsx   # QueryClientProvider y BrowserRouter
│   │   └── router.tsx      # Definición de rutas principales
│   ├── features/           # Módulos por paquete de casos de uso
│   │   ├── seguridad/      # Paquete P1: Seguridad y Administración (CU-01 … CU-08)
│   │   ├── deportivo/      # Paquete P2: Gestión Deportiva (CU-09 … CU-17)
│   │   ├── vision/         # Paquete P3: Visión por Computadora (CU-18 … CU-29)
│   │   ├── partido/        # Paquete P4: Operación del Partido (CU-30 … CU-39)
│   │   ├── analisis/       # Paquete P5: Análisis Táctico (CU-40 … CU-48)
│   │   └── asistencia/     # Paquete P6: Asistencia y Reportes (CU-49 … CU-58)
│   ├── shared/             # Código compartido entre features
│   │   ├── api/            # Cliente Axios único e interceptores de autenticación
│   │   ├── config/         # Configuración y validación de variables de entorno (env.ts)
│   │   ├── lib/            # Utilidades y funciones puras compartidas
│   │   └── ui/             # Componentes base reutilizables de UI (Pendiente, etc.)
│   ├── index.css           # Estilos base y variables de diseño
│   └── main.tsx            # Punto de entrada de React (montaje en #root)
├── .env.example            # Plantilla de variables de entorno versionada
├── .env.local              # Variables de entorno locales (ignorado por Git)
├── eslint.config.js / .oxlintrc.json  # Configuración del linter
├── package.json            # Dependencias y scripts del proyecto
├── tsconfig.app.json       # Configuración de compilación para la aplicación
├── tsconfig.json           # Configuración raíz con referencias de proyectos
└── vite.config.ts          # Configuración de Vite y resolución de alias
```

---

## Guía de Carpetas: Qué va y qué NO va

### `src/features/<nombre>/`

Representa un paquete del sistema de información según el modelo de casos de uso.

- **Qué va:**
  - `pages/`: Vistas y pantallas correspondientes al paquete.
  - `components/`: Componentes que **solo** tienen sentido dentro de este módulo.
  - `api.ts`: Consultas y mutaciones hacia los endpoints de este módulo.
  - `types.ts`: Tipos del dominio e interfaces de datos de este paquete.
  - `index.ts`: Punto de exportación público de la feature.
- **Qué NO va:**
  - 🚫 **Una feature NUNCA debe importar de otra feature.** Si dos features necesitan un componente, tipo o función común, debe promoverse a `src/shared/`.
  - 🚫 No debe contener configuraciones globales ni inicialización de clientes HTTP.

### `src/shared/ui/`

- **Qué va:**
  - Componentes de interfaz de usuario atómicos y reutilizables por múltiples features (ej. `Pendiente.tsx`, botones, modales, tablas genéricas).
- **Qué NO va:**
  - 🚫 Componentes con lógica acoplada a un caso de uso particular.
  - 🚫 NO crear ni usar `shared/components/`; toda la UI común reside en `shared/ui/`.

### `src/shared/api/`

- **Qué va:**
  - Cliente Axios centralizado (`client.ts`), interceptores para manejo de tokens JWT y errores 401.
- **Qué NO va:**
  - 🚫 Llamadas de dominio específicas (deben ir en el `api.ts` de cada feature).

### `src/shared/config/`

- **Qué va:**
  - Configuración del entorno (`env.ts`).
- **Qué NO va:**
  - 🚫 Constantes que pertenezcan a las reglas de negocio de una feature en específico.

### `src/shared/lib/`

- **Qué va:**
  - Funciones de formateo, helpers de fechas, validadores puros y utilidades matemáticas o de cadenas compartidas.
- **Qué NO va:**
  - 🚫 Componentes visuales ni llamadas a APIs.
