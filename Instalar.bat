@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalar CalificaTAP
echo.
echo  ==============================================
echo    Instalando CalificaTAP (necesita internet)
echo  ==============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo  [X] No se encontro Python.
  echo      Descarguelo de https://www.python.org/downloads/
  echo      y al instalar marque la casilla "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if exist "externo\OMRChecker\requirements.txt" (
  python -m pip install -r "externo\OMRChecker\requirements.txt"
) else (
  echo.
  echo  [!] No se encontro externo\OMRChecker. El lector ^(Modulo 2^) lo necesitara.
)
echo.
echo  Listo. Ahora abra CalificaTAP con doble clic en "Abrir CalificaTAP.bat".
echo.
pause
