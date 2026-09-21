@echo off
echo ============================================================
echo  CORTEX Content Agent ^| Port 8002
echo ============================================================

cd /d "%~dp0"

:: Try to activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [INFO] No .venv found. Using system Python.
    echo [TIP]  Run: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
)

echo.
echo Starting Content Agent on http://localhost:8002
echo Swagger Docs: http://localhost:8002/docs
echo Health Check: http://localhost:8002/health
echo.

uvicorn app.main:app --reload --port 8002 --host 0.0.0.0

pause
