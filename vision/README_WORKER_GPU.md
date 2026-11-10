# Guía de Instalación y Ejecución del Worker de Visión en GPU

Esta guía está diseñada para el integrante del equipo que dispone de una laptop/PC con tarjeta gráfica **NVIDIA** (RTX 3050, 3060, 4060 o superior).

---

## 1. Requisitos previos en la laptop con GPU

1. **Drivers NVIDIA actualizados**:
   - Descargar los controladores Game Ready o Studio más recientes desde [nvidia.com/drivers](https://www.nvidia.com/Download/index.aspx).
2. **Python 3.10, 3.11 o 3.12** instalado (marcar *"Add python.exe to PATH"* durante la instalación).
3. **Git** para clonar el repositorio.

---

## 2. Preparar el entorno virtual con PyTorch CUDA

Abre una terminal (`PowerShell` o `cmd`) en la carpeta raíz del proyecto `Deportivo`:

```bash
# 1. Crear el entorno virtual si no existe
python -m venv venv_gpu

# 2. Activar el entorno virtual
# En Windows PowerShell:
.\venv_gpu\Scripts\Activate.ps1
# En Windows CMD:
.\venv_gpu\Scripts\activate.bat

# 3. Instalar PyTorch compilado con soporte CUDA 12.1 (o 11.8)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 4. Instalar las dependencias de visión (YOLO, OpenCV, etc.)
pip install ultralytics opencv-python numpy requests pydantic httpx
```

### Comprobar que PyTorch reconoce la GPU:

Ejecuta en la terminal:
```bash
python -c "import torch; print('CUDA disponible:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO')"
```
Debe responder:
`CUDA disponible: True | GPU: NVIDIA GeForce RTX ...`

---

## 3. Conexión y Ejecución del Worker

El worker no necesita tener la base de datos PostgreSQL ni el backend corriendo localmente; puede conectarse al backend que está corriendo en la máquina del servidor (o la de Daniel) mediante su IP local o red Wi-Fi compartida.

### Opción A · Usando el script interactivo:
Haz doble clic en:
`iniciar_worker_gpu.bat`

Te pedirá:
1. **URL del backend**: Si está en la misma máquina pon `http://localhost:8000/api`. Si está en otra laptop en la misma red Wi-Fi, pon la IP local (ejemplo: `http://192.168.1.15:8000/api`).
2. **Email de usuario**: Un usuario con rol `ADMIN` o `ANALISTA` (por defecto: `admin@ejemplo.com`).
3. **Contraseña**: (por defecto: `admin1234`).
4. **Dispositivo**: `cuda:0`.

### Opción B · Desde la línea de comandos:

```bash
cd vision
python -m procesamiento.worker --api http://192.168.1.15:8000/api --email admin@ejemplo.com --password admin1234 --dispositivo cuda:0
```

---

## 4. ¿Cómo funciona el flujo de trabajo?

1. En la aplicación web (Frontend), subes un video de un partido y haces clic en **"Procesar video"**.
2. El video queda en la cola del backend con estado `PROCESANDO`.
3. El worker en tu laptop detecta el trabajo, descarga el video automáticamente, procesa los cuadros acelerado por tu GPU NVIDIA (a más de 30-60 FPS), calcula homografía, seguimiento de jugadores y detección del balón.
4. Va enviando lotes de resultados al backend y actualizando el porcentaje de progreso (`progreso_pct`).
5. Al terminar, el video queda en estado `PROCESADO (100 %)` y la telemetría real queda disponible inmediatamente en el visor y el radar 2D.

