@echo off
cd /d "%~dp0..\frontend"
if "%PORT%"=="" set PORT=8088
echo [frontend] http://127.0.0.1:%PORT%
call npm run dev -- --host 0.0.0.0 --port %PORT%
echo.
echo [frontend] stopped. press any key to close.
pause >nul
