@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "ISCC="
set "LOG=%CD%\RESULTAT-BUILD-INSTALLATEUR.txt"
>"%LOG%" echo Fabrication installateur G-Skol - %DATE% %TIME%

if not exist "G-Skol.iss" goto NOISS
if not exist "dist\G-Skol-Portable\G-Skol.exe" goto NOPORTABLE

where ISCC.exe >nul 2>&1
if not errorlevel 1 set "ISCC=ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC goto NOINNO

rem This script uses the existing G-Skol.iss and does not modify the Core.
echo Fabrication de l'installateur en cours...
"%ISCC%" "G-Skol.iss" >>"%LOG%" 2>&1
if errorlevel 1 goto BUILDFAIL
if not exist "dist\G-Skol-Installation.exe" goto BUILDFAIL
echo.
echo Installateur pret :
echo "%CD%\dist\G-Skol-Installation.exe"
explorer "%CD%\dist"
goto END

:NOISS
echo Fichier G-Skol.iss introuvable a cote du batch.
goto FAIL
:NOPORTABLE
echo Le portable n'existe pas encore.
echo Lancez d'abord 002-CREER-G-SKOL-PORTABLE.bat.
goto FAIL
:NOINNO
echo Inno Setup 6 ou 7 est introuvable.
echo https://jrsoftware.org/isdl.php
goto FAIL
:BUILDFAIL
echo Echec de creation de l'installateur. Voir "%LOG%".
goto FAIL
:FAIL
echo La fabrication a echoue.
:END
pause
endlocal
