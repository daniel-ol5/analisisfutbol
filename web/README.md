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

---

## Sesión, login y registro (feature `seguridad`)

Rutas públicas: `/login` (CU-02) y `/registro` (CU-01). Tras iniciar sesión o registrarse con éxito se redirige a `/`.

### Piezas

| Archivo (en `src/features/seguridad/`) | Para qué sirve |
| --- | --- |
| `session.ts` | Único módulo que guarda y lee `{ access_token, usuario }`: `iniciarSesion`, `cerrarSesion`, `obtenerSesion` y el hook `useSesion`. |
| `api.ts` | `login`, `registrar` y `logout` contra `/seguridad/*`. |
| `errors.ts` | Convierte el error del backend (`detail` como texto o como lista 422) en un mensaje legible en español. |
| `validation.ts` | Validaciones de formulario y normalización del email. |
| `components/BotonCerrarSesion.tsx` | Llama a `POST /seguridad/logout` y limpia la sesión aunque la llamada falle. Está exportado, pero no se monta en ninguna pantalla todavía. |

### Cómo funciona

- **Token:** el cliente de `shared/api/client.ts` adjunta `Authorization: Bearer <access_token>` si hay sesión. `shared/` no importa de ninguna feature: `session.ts` le registra un adaptador (`registrarAdaptadorAuth`) al cargarse.
- **401:** en una ruta protegida significa sesión caída; se limpia la sesión y se redirige a `/login` con `window.location.assign`. En `/seguridad/login` y `/seguridad/registro` el 401 NO redirige: se muestra en el formulario.
- **No hay refresh:** el backend emite `refresh_token` pero no tiene endpoint que lo consuma, así que la web no intenta renovar el token (dura 15 min).
- **Email:** en login y registro se recorta y se pasa a minúsculas antes de enviarlo, porque el backend no lo normaliza.
- **Contraseña (registro):** de 8 a 72 caracteres y como máximo 72 bytes en UTF-8 (límite de bcrypt).
- **Dónde se guarda:** `localStorage` (clave `areatecnica.sesion`). Hay un TODO en `session.ts` para revisarlo cuando exista refresh.
- **Mock o API real:** cambiar solo `VITE_API_URL` en `.env.local` (`http://127.0.0.1:8000/api` o `http://127.0.0.1:4010/api`).
- **Guardas de ruta:** todavía no existen; abrir `/` sin sesión no redirige. Solo un 401 de la API cierra la sesión.

---

## Guía de montaje de cámara (feature `vision`, CU-18)

Pantalla estática en `/vision/guia-montaje`. No llama a la API. Por ahora solo se abre escribiendo la URL: no hay menú ni enlace desde `VisionPage`.

| Archivo (en `src/features/vision/`) | Para qué sirve |
| --- | --- |
| `guia.ts` | Único lugar con los valores: datos recomendados, tamaños de referencia y los ítems de la lista. Los valores salen de `docs/adr/ADR-001-montaje-de-camara.md`. Lo que el ADR deja en blanco es `null` y se muestra «Por definir». |
| `pages/GuiaMontajePage.tsx` | La pantalla. |
| `components/ListaComprobacion.tsx` | Casillas con contador «X de Y completados» y aviso cuando todo está marcado. El estado no se guarda: al recargar se reinicia. |
| `components/EsquemaMontaje.tsx` | Esquemas SVG (vista desde arriba y vista lateral). Son ilustrativos y no están a escala. |
| `guia.css` | Estilos con prefijo `guia-`. |

- **Ítems de la lista:** los de `ITEMS_ADR` vienen del ADR. Los de `ITEMS_PROPUESTA` no: están marcados «Por confirmar» hasta que el equipo los apruebe.
- **Aviso de estado del ADR:** `AVISO_ESTADO_ADR` en `guia.ts` muestra que el ADR sigue «pendiente de decisión». Cuando se cierre, ponerlo en `null` quita el aviso.
- **Botón «Ir a calibrar»:** está deshabilitado a propósito; la pantalla de calibración es otra tarea.
