# Pruebas extremo a extremo (T-093)

Tres flujos críticos con Playwright, contra el backend y la web levantados de verdad:

| Archivo | Flujo |
|---|---|
| `1-calibracion.e2e.ts` | Iniciar sesión, calibrar la cámara y ver el plano 2D |
| `2-vivo-recomendacion.e2e.ts` | Partido en vivo (emisor simulado) hasta que llega una recomendación |
| `3-video-informe.e2e.ts` | Subir un video hasta «Procesado». El informe queda pendiente (T-098, T-100) |

En la CI los corre el job `e2e` de `.github/workflows/ci.yml`.

## En local

Hace falta una base **exclusiva** cuyo nombre contenga `e2e` (el script de siembra se
niega a usar otra). Con la base de pruebas de Docker:

```sh
docker compose --profile test up -d db_test
docker compose exec db_test createdb -U postgres areatecnica_e2e

# backend (en backend/)
export DATABASE_URL=postgresql+asyncpg://postgres:<TEST_DB_PASSWORD>@localhost:55432/areatecnica_e2e
export CORS_ORIGINS=http://127.0.0.1:5180
alembic upgrade head
E2E_SEMBRAR=1 python scripts/sembrar_e2e.py --salida /tmp/e2e/datos.json --video /tmp/e2e/clip.mp4
uvicorn app.main:app --port 8100

# web (en web/, otra terminal)
VITE_API_URL=http://127.0.0.1:8100/api npx vite --port 5180 --strictPort

# pruebas (en web/, otra terminal)
npx playwright install chromium          # la primera vez
E2E_DATOS=/tmp/e2e/datos.json E2E_PYTHON=../backend/venv/bin/python npm run e2e
```

Si la descarga del «headless shell» de Chromium se traba (mala conexión) y ya tienes
el Chromium completo de la misma versión, agrega `E2E_CANAL=chromium`: usa ese
navegador en modo sin cabeza. En la CI no hace falta.

Los datos sembrados se gastan (los partidos se inician y calibran): para repetir,
borra la base (`dropdb`/`createdb`) y vuelve a sembrar.
