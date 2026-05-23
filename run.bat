@echo off
REM ===========================================================
REM  Aquarium 98 - Windows launcher
REM  Creates .venv on first run, installs deps, then launches.
REM ===========================================================
setlocal
cd /d "%~dp0"

set "PY=python"
where %PY% >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Install Python 3.9+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo ERROR: failed to create .venv
        pause
        exit /b 1
    )
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip install failed
        pause
        exit /b 1
    )
)

start "" /B ".venv\Scripts\pythonw.exe" aquarium.py %*
endlocal
