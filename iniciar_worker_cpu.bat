@echo off
chcp 65001 > nul
echo =====================================================================
echo  Iniciando Worker de Vision Artificial (Modo CPU Local)
echo =====================================================================
echo.

set /p API_URL="URL del backend (por defecto http://localhost:8000/api): "
if "%API_URL%"=="" set API_URL=http://localhost:8000/api

set /p EMAIL="Email de analista o admin de tu club (por defecto realbetis@gmail.com): "
if "%EMAIL%"=="" set EMAIL=realbetis@gmail.com

set /p PASS="Contraseña del usuario (por defecto 12345678): "
if "%PASS%"=="" set PASS=12345678

cd vision
echo.
echo Conectando worker a %API_URL% usando CPU...
python -m procesamiento.worker --api %API_URL% --email %EMAIL% --password %PASS% --dispositivo cpu --clases futbol

pause

