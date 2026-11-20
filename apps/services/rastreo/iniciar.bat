@echo off
cd /d "%~dp0"
REM PEDIDOS_BASE_URL apunta al microservicio pedidos (local o GCP)
if "%PEDIDOS_BASE_URL%"=="" set PEDIDOS_BASE_URL=http://127.0.0.1:5004
python app.py
