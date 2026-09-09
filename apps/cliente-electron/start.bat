@echo off
title Lanzador Cliente Electron XML - UDEM SC3705
echo ======================================================================
echo  CLIENTE DE ESCRITORIO ELECTRON - CONSUMO XML CLOUD (PROMPT 04)
echo  Estudiante: Fabian Azaed Orta Singlaterry (Matricula: 613504)
echo  Materia: Integracion de Aplicaciones Computacionales (SC-2236)
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Verificando Node.js y npm...
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js no esta instalado o no se encuentra en el PATH.
    echo Por favor instale Node.js desde https://nodejs.org/
    pause
    exit /b 1
)

echo [2/3] Verificando dependencias locales de Electron...
if not exist "node_modules\electron" (
    echo Instalando Electron localmente via npm...
    call npm install electron --save-dev
)

echo [3/3] Iniciando aplicacion de escritorio Electron...
call npx electron .
