@echo off
title Catalogo de Libros Electron - Windows 11 (UDEM SC-2236)
color 0b
echo =====================================================================
echo  CATALOGO DE LIBROS ELECTRON (WINDOWS 11) - UDEM SC-2236
echo  Estudiante: Fabian Azaed Orta Singlaterry (Matricula: 613504)
echo =====================================================================
echo.
echo Iniciando aplicacion Electron...
echo.

if not exist "node_modules" (
    echo [INFO] Primera ejecucion detectada. Copiando/instalando dependencias...
    call npm.cmd install
)

call npm.cmd start
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [AVISO] Intentando ejecucion directa con npx...
    call npx.cmd electron .
)
pause
