@echo off
setlocal
chcp 65001 > nul
echo Worker de vision - cpu
echo Consulta GUIA_PRUEBAS_LAPTOP_GPU.md para preparar el entorno.
set /p API_URL="URL de la API (por defecto http://127.0.0.1:8000/api): "
if "%API_URL%"=="" set API_URL=http://127.0.0.1:8000/api
set /p EMAIL="Email del analista o administrador: "
cd /d "%~dp0vision"
python -m procesamiento.worker --api "%API_URL%" --email "%EMAIL%" --dispositivo cpu --clases futbol
pause
endlocal
