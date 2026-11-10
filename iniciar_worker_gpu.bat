@echo off
chcp 65001 > nul
echo =====================================================================
echo  Iniciando Worker de Vision Artificial (Acelerado por GPU NVIDIA)
echo =====================================================================
echo.

set /p API_URL="URL del backend (por defecto http://localhost:8000/api): "
if "%API_URL%"=="" set API_URL=http://localhost:8000/api

set /p EMAIL="Email de analista o admin de tu club (por defecto realbetis@gmail.com): "
if "%EMAIL%"=="" set EMAIL=realbetis@gmail.com

set /p PASS="Contraseña del usuario (por defecto 12345678): "
if "%PASS%"=="" set PASS=12345678

set /p GPU_ID="Dispositivo GPU (por defecto cuda:0): "
if "%GPU_ID%"=="" set GPU_ID=cuda:0

cd vision
echo.
echo Conectando worker a %API_URL% usando %GPU_ID%...
python -m procesamiento.worker --api %API_URL% --email %EMAIL% --password %PASS% --dispositivo %GPU_ID% --clases futbol

pause

