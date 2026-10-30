@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
py -3.11 "PREPARER-VERSION-G-SKOL.py"
if errorlevel 1 (
  echo.
  echo La personnalisation a echoue. Aucun build n'a ete lance.
)
pause
endlocal
