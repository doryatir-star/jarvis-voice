@echo off
setlocal
cd /d "%~dp0"

echo === Jarvis build ===

REM Use a venv OUTSIDE OneDrive (Store-Python can't create venvs on OneDrive reliably).
REM Use C:\Users\Public — Store-Python redirects %LOCALAPPDATA% and %APPDATA%.
set "VROOT=C:\Users\Public\JarvisBuild"
set "VENV=%VROOT%\venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo [build] Creating virtualenv at %VENV% ...
    if not exist "%VROOT%" mkdir "%VROOT%"
    python -m venv "%VENV%" || goto :err
)

set "PY=%VENV%\Scripts\python.exe"
set "PIP=%VENV%\Scripts\pip.exe"

echo [build] Upgrading pip...
"%PY%" -m pip install --upgrade pip >nul || goto :err

echo [build] Installing dependencies...
"%PIP%" install -r requirements.txt || goto :err
"%PIP%" install pyinstaller pillow || goto :err

echo [build] Generating icon...
"%PY%" make_icon.py || goto :err

echo [build] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "Jarvis.spec" del /q "Jarvis.spec"

echo [build] Running PyInstaller (takes a minute) ...
"%VENV%\Scripts\pyinstaller.exe" ^
  --noconfirm --onefile --windowed ^
  --name Jarvis ^
  --icon jarvis.ico ^
  --add-data "jarvis.ico;." ^
  --collect-all speech_recognition ^
  --collect-all pyaudio ^
  --collect-all pyttsx3 ^
  --collect-all comtypes ^
  --hidden-import pyttsx3.drivers ^
  --hidden-import pyttsx3.drivers.sapi5 ^
  main.py || goto :err

if not exist "dist\Jarvis.exe" goto :err

echo [build] Copying Jarvis.exe to Desktop...
copy /y "dist\Jarvis.exe" "%USERPROFILE%\OneDrive\Desktop\Jarvis.exe" >nul
if errorlevel 1 copy /y "dist\Jarvis.exe" "%USERPROFILE%\Desktop\Jarvis.exe" >nul

echo.
echo === SUCCESS ===
echo Jarvis.exe is on your Desktop. Double-click to run.
echo (Optional) create %%APPDATA%%\Jarvis\.env with ANTHROPIC_API_KEY=... for smart mode.
echo.
pause
goto :eof

:err
echo.
echo [build] FAILED — see errors above.
pause
exit /b 1
