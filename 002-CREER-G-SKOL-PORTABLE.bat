@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PYTHON=py -3.11"
set "APPNAME=G-Skol"
set "DEST=%CD%\dist\G-Skol-Portable"
set "ZIP=%CD%\dist\G-Skol-Portable.zip"
set "LOG=%CD%\RESULTAT-BUILD-G-SKOL.txt"
set "PUBLIC_LIBRARY=%CD%\BibliothequePublique\Modèles de Fiches"

>"%LOG%" echo Fabrication G-Skol portable - %DATE% %TIME%
if not exist "app.py" goto MISSING
if not exist "assets\G-Skol.ico" goto MISSING
if not exist "requirements.txt" goto MISSING
if not exist "gskol_make_portable_zip.py" goto MISSING
if not exist "ModelesOfficiels\minerals.db" goto MISSING
rem Required public distribution documents: stop before compilation if missing.
for %%F in (LICENSE LICENCES-TIERS.md SOURCES-DONNEES.md) do (
  if not exist "%%F" (
    echo ERREUR : document obligatoire absent : %%F
    >>"%LOG%" echo ERREUR : document obligatoire absent : %%F
    goto NOTICEFAIL
  )
)

%PYTHON% --version >>"%LOG%" 2>&1
if errorlevel 1 goto NOPYTHON
%PYTHON% -m pip install --disable-pip-version-check -r requirements.txt pyinstaller >>"%LOG%" 2>&1
if errorlevel 1 goto DEPENDENCIES
%PYTHON% -m compileall -q app.py core ui >>"%LOG%" 2>&1
if errorlevel 1 goto SYNTAX

if exist "build" rmdir /s /q "build" >>"%LOG%" 2>&1
if exist "dist\%APPNAME%" rmdir /s /q "dist\%APPNAME%" >>"%LOG%" 2>&1
if exist "%DEST%" rmdir /s /q "%DEST%" >>"%LOG%" 2>&1
if exist "%ZIP%" del /q "%ZIP%" >>"%LOG%" 2>&1
if exist "%APPNAME%.spec" del /q "%APPNAME%.spec" >>"%LOG%" 2>&1

if not exist "dist" mkdir "dist"
echo Fabrication de G-Skol.exe en cours...
set "DATA=--add-data assets\G-Skol.ico;assets --add-data ModelesOfficiels;ModelesOfficiels"
if exist "ui\access_data_bridge.vbs" set "DATA=%DATA% --add-data ui\access_data_bridge.vbs;ui"
if exist "ui\access_forms_structure_bridge.vbs" set "DATA=%DATA% --add-data ui\access_forms_structure_bridge.vbs;ui"
if exist "ui\access_structure_bridge.vbs" set "DATA=%DATA% --add-data ui\access_structure_bridge.vbs;ui"
%PYTHON% -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name "%APPNAME%" --icon "assets\G-Skol.ico" %DATA% "app.py" >>"%LOG%" 2>&1
if errorlevel 1 goto BUILDFAIL
if not exist "dist\%APPNAME%\%APPNAME%.exe" goto BUILDFAIL
move "dist\%APPNAME%" "%DEST%" >>"%LOG%" 2>&1
if errorlevel 1 goto BUILDFAIL

rem PyInstaller usually includes Python DLL; repair only if needed.
if not exist "%DEST%\_internal\python311.dll" (
  for /f "delims=" %%P in ('%PYTHON% -c "import sys; print(sys.base_prefix)"') do set "PYBASE=%%P"
  if exist "%PYBASE%\python311.dll" copy /y "%PYBASE%\python311.dll" "%DEST%\_internal\python311.dll" >>"%LOG%" 2>&1
)
if not exist "%DEST%\_internal\python311.dll" goto BUILDFAIL
type nul >"%DEST%\G-Skol.portable"

rem Never copy the personal Workspace into a public distribution.
if exist "%PUBLIC_LIBRARY%\" (
  if not exist "gskol_copy_library.py" goto MISSING
  echo Copie de la bibliotheque publique supplementaire...
  %PYTHON% "gskol_copy_library.py" --public "%PUBLIC_LIBRARY%" "%DEST%\Workspace" >>"%LOG%" 2>&1
  if errorlevel 1 goto LIBRARYFAIL
) else (
  >>"%LOG%" echo BibliothequePublique absente : seuls les ModelesOfficiels sont inclus.
)

(
echo G-SKOL - VERSION PORTABLE
echo.
echo Extraire tout le ZIP, puis lancer G-Skol.exe.
echo Conserver le dossier _internal avec l'executable.
echo Les modeles officiels integres sont fournis.
echo Les autres dossiers du Workspace seront crees au premier lancement.
echo Pour tester vos collections, copier uniquement les .coldb voulus dans Workspace\Collections.
) >"%DEST%\LISEZ-MOI.txt"

rem Copy all three mandatory documents into the portable distribution.
for %%F in (LICENSE LICENCES-TIERS.md SOURCES-DONNEES.md) do (
  copy /y "%%F" "%DEST%\%%F" >>"%LOG%" 2>&1
  if errorlevel 1 goto NOTICEFAIL
)

%PYTHON% "gskol_make_portable_zip.py" "%DEST%" "%ZIP%" >>"%LOG%" 2>&1
if errorlevel 1 goto ZIPFAIL
if not exist "%ZIP%" goto ZIPFAIL
echo.
echo G-Skol portable pret :
echo "%ZIP%"
echo.
echo Verifier les avertissements eventuels dans "%LOG%".
explorer "%CD%\dist"
goto END

:MISSING
echo Fichier necessaire absent du Core. Voir "%LOG%".
goto FAIL
:NOPYTHON
echo Python 3.11 est introuvable. Voir "%LOG%".
goto FAIL
:DEPENDENCIES
echo Installation des dependances impossible. Voir "%LOG%".
goto FAIL
:SYNTAX
echo Erreur de syntaxe Python dans le Core. Voir "%LOG%".
goto FAIL
:BUILDFAIL
echo Echec PyInstaller. Voir "%LOG%".
goto FAIL
:ZIPFAIL
echo Echec creation du ZIP. Voir "%LOG%".
goto FAIL
:LIBRARYFAIL
echo Echec copie bibliotheque publique. Voir "%LOG%".
goto FAIL
:NOTICEFAIL
echo Documents de licence absents ou impossibles a copier. Voir "%LOG%".
goto FAIL
:FAIL
echo La fabrication a echoue.
:END
pause
endlocal
