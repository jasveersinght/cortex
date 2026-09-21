@echo off
echo.
echo  ████████╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗
echo  ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝
echo  ██║     ██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝ 
echo  ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗ 
echo  ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗
echo   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
echo.
echo  JA Assure AI Intelligence Ecosystem
echo  ===========================================
echo.

REM Start Research Agent (Ja_assure_vertex)
echo [1/3] Starting Research Agent on port 8000...
start "CORTEX - Research Agent" cmd /k "cd /d ..\Ja_assure_vertex && call venv\Scripts\activate && uvicorn app.main:app --port 8000 --reload"

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start CORTEX Gateway (compliance + proxy)
echo [2/3] Starting CORTEX Gateway on port 8001...
start "CORTEX - Gateway" cmd /k "pip install -q -r requirements.txt && uvicorn main:app --port 8001 --reload"

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Open frontend
echo [3/3] Opening CORTEX Frontend...
start "" "..\frontend\index.html"

echo.
echo  CORTEX is starting up:
echo.
echo  Research Agent:   http://localhost:8000
echo  CORTEX Gateway:   http://localhost:8001
echo  Frontend:         Open index.html in browser
echo  API Docs:         http://localhost:8001/docs
echo.
echo  Press any key in this window to stop...
pause
