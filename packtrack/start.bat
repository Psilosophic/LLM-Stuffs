@echo off
REM PackTrack launcher for Windows. Double-click to run.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo Install from https://www.python.org/downloads/ and check "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [setup] Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [setup] Installing / updating dependencies...
pip install -q -r requirements.txt

if "%OPENAI_API_KEY%"=="" (
    echo.
    echo [note] OPENAI_API_KEY is not set. You can still use the Labels page.
    echo        To process video, set it first:  setx OPENAI_API_KEY "sk-..."
    echo.
)

echo.
echo Opening PackTrack in your browser...
start "" "http://localhost:5001/labels"
python app.py

pause
