@echo off
cd /d "%~dp0..\backend"
if "%PORT%"=="" set PORT=8001
set PYTHONUNBUFFERED=1
echo [backend] http://127.0.0.1:%PORT%
python -u -m uvicorn app.main:app --reload --host 127.0.0.1 --port %PORT%
echo.
echo [backend] stopped. press any key to close.
pause >nul
