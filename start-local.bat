@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
echo.
echo  qc-hub local start
echo  backend  http://127.0.0.1:8001
echo  frontend http://127.0.0.1:8088
echo.
netstat -ano | findstr ":8001" | findstr "LISTENING" >nul && echo  [warn] 8001 already listening
netstat -ano | findstr ":8088" | findstr "LISTENING" >nul && echo  [warn] 8088 already listening
start "qc-hub-backend" "%ROOT%\scripts\run-backend.bat"
timeout /t 3 /nobreak >nul
start "qc-hub-frontend" "%ROOT%\scripts\run-frontend.bat"
timeout /t 4 /nobreak >nul
start "" http://127.0.0.1:8088
endlocal
