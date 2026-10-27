@echo off
cd /d "%~dp0"
rem Abre la aplicacion sin dejar la ventana negra abierta
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw "CalificaTAP.pyw"
  exit /b
)
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw "CalificaTAP.pyw"
  exit /b
)
echo No se encontro Python. Ejecute primero Instalar.bat
pause
