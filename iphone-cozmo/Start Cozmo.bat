@echo off
REM Double-click this to start Cozmo. Keep cozmo_all_in_one.py next to it.
title Cozmo
cd /d "%~dp0"

echo Starting Cozmo...
echo.

REM Try the py launcher first (how Python usually installs itself on
REM Windows), then plain python, so this works either way.
where py >nul 2>nul
if %errorlevel%==0 (
    py cozmo_all_in_one.py
    goto done
)

where python >nul 2>nul
if %errorlevel%==0 (
    python cozmo_all_in_one.py
    goto done
)

echo.
echo ============================================================
echo  Python isn't installed on this computer.
echo.
echo  Get it from https://www.python.org/downloads/
echo  IMPORTANT: tick "Add Python to PATH" on the first screen
echo  of the installer, then run this again.
echo ============================================================

:done
echo.
echo Cozmo has stopped. Press any key to close this window.
pause >nul
