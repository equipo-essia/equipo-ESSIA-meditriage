@echo off
rem Lanzador portable de MediTriage para Windows: doble clic en este archivo.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 start_demo.py %*
  goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python start_demo.py %*
  goto :end
)

where python3 >nul 2>nul
if %errorlevel%==0 (
  python3 start_demo.py %*
  goto :end
)

echo.
echo ERROR: no se encontro Python 3.10 o superior.
echo Instalalo desde https://www.python.org/downloads/ y vuelve a ejecutar.
echo.
pause

:end
