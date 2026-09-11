@echo off
REM Double-click this ONCE to turn cozmo_all_in_one.py into a real
REM standalone Cozmo.exe that runs without Python installed.
REM An .exe has to be built on Windows itself, which is why this is a
REM script you run rather than a file that could just be handed to you.
title Building Cozmo.exe
cd /d "%~dp0"

echo Building Cozmo.exe -- this takes a few minutes the first time.
echo.

set PY=
where py >nul 2>nul && set PY=py
if "%PY%"=="" ( where python >nul 2>nul && set PY=python )

if "%PY%"=="" (
    echo Python isn't installed. Get it from https://www.python.org/downloads/
    echo Tick "Add Python to PATH" in the installer, then run this again.
    goto done
)

echo Installing the builder...
%PY% -m pip install --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo Couldn't install PyInstaller. You need internet for this one step.
    goto done
)

echo Building...
%PY% -m PyInstaller --onefile --console --name Cozmo cozmo_all_in_one.py
if errorlevel 1 (
    echo Build failed -- see the messages above.
    goto done
)

echo.
echo ============================================================
echo  Done. Your app is:   dist\Cozmo.exe
echo  Copy it anywhere and double-click it to run.
echo ============================================================

:done
echo.
pause
