@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\" (
    echo [Jarvis] Creating virtual environment...
    python -m venv .venv || goto :err
)

call ".venv\Scripts\activate.bat" || goto :err

if not exist ".venv\.installed" (
    echo [Jarvis] Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt || goto :err
    echo done > ".venv\.installed"
)

if not exist ".env" (
    if exist ".env.example" copy /y ".env.example" ".env" >nul
    echo [Jarvis] Created .env — edit it to add your ANTHROPIC_API_KEY for smart mode.
)

python main.py
goto :eof

:err
echo [Jarvis] Setup failed. Make sure Python 3.10+ is installed and on PATH.
pause
exit /b 1
