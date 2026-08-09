@echo off
echo.
echo  Rank ^& Rent Deployer
echo  ----------------------
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".deps_installed" (
    echo  Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo installed > .deps_installed
)

REM Check for .env
if not exist ".env" (
    echo  No .env file found. Copying from .env.example...
    copy .env.example .env
    echo.
    echo  IMPORTANT: Open .env and add your API keys before using the tool.
    echo  Then run start.bat again.
    echo.
    pause
    exit /b 0
)

echo  Starting server...
echo  Open http://localhost:5000 in your browser.
echo.
python server.py
pause
