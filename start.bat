@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  质控通管理系统 (qc-hub)
echo  Backend : http://127.0.0.1:8001
echo  Frontend: http://172.16.122.175:8088
echo.

start "qc-hub-backend" cmd /k "call conda activate excel-to-web && cd /d "%ROOT%\backend" && set PYTHONUNBUFFERED=1 && python -u -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001 --log-level info"

timeout /t 2 /nobreak >nul

start "qc-hub-frontend" cmd /k "nvm use 20.19.0 && cd /d "%ROOT%\frontend" && set VITE_DEV_BACKEND=http://127.0.0.1:8001 && if not exist node_modules npm install && npm run dev -- --host 0.0.0.0 --port 8088"

timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8088

endlocal
