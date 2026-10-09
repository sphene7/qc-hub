@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  qc-hub first-time setup
echo.

where conda >nul 2>&1
if errorlevel 1 (
  echo ERROR: conda not found. Install Anaconda/Miniconda first.
  exit /b 1
)

call conda env update -n excel-to-web -f "%ROOT%\environment.yml" --prune
if errorlevel 1 (
  echo Trying conda env create...
  call conda env create -f "%ROOT%\environment.yml"
)

where nvm >nul 2>&1
if errorlevel 1 (
  echo ERROR: nvm not found. Install nvm-windows first.
  exit /b 1
)

call nvm use 20.19.0
cd /d "%ROOT%\frontend"
call npm install

echo.
echo  Setup done. Run: start.bat
echo.

endlocal
