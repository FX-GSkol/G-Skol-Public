@echo off
chcp 65001 >nul
cd /d "%~dp0"
py diagnostic_launcher.py %*
if errorlevel 1 (
  echo.
  echo G-Skol s'est arrete avec une erreur.
  echo Consultez Workspace\Journaux\mm3.log si necessaire.
  pause
)
