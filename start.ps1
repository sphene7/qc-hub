$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$CondaEnv = "excel-to-web"
$NodeVersion = "20.19.0"
$BackendPort = 8001
$FrontendPort = 8088

$condaExe = @(
    $env:CONDA_EXE
    "$env:USERPROFILE\anaconda3\Scripts\conda.exe"
    "$env:USERPROFILE\miniconda3\Scripts\conda.exe"
    "C:\Users\Sphene\anaconda3\Scripts\conda.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $condaExe) {
    throw "找不到 conda.exe，请确认 Anaconda / Miniconda 已安装"
}

$nvmCmd = Get-Command nvm -ErrorAction SilentlyContinue
if (-not $nvmCmd) {
    throw "找不到 nvm，请确认 nvm-windows 已安装并在 PATH 中"
}

Write-Host "质控通管理系统"
Write-Host "conda env : $CondaEnv"
Write-Host "node      : $NodeVersion (nvm)"
Write-Host "Starting backend  http://127.0.0.1:$BackendPort"
Write-Host "Starting frontend http://172.16.122.175:$FrontendPort"

$backendCmd = @"
`$ErrorActionPreference = 'Stop'
(& '$condaExe' 'shell.powershell' 'hook') | Out-String | Invoke-Expression
conda activate $CondaEnv
if (`$env:CONDA_DEFAULT_ENV -ne '$CondaEnv') { throw "conda activate $CondaEnv 失败" }
Set-Location '$PSScriptRoot\backend'
Write-Host ('Python = ' + (python -c 'import sys; print(sys.executable)'))
`$env:PYTHONUNBUFFERED = '1'
python -u -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort --log-level info
"@

$frontendCmd = @"
`$ErrorActionPreference = 'Stop'
nvm use $NodeVersion
Set-Location '$PSScriptRoot\frontend'
if (-not (Test-Path 'node_modules')) {
    Write-Host 'npm install ...'
    npm install
}
Write-Host ('Node = ' + (node -v) + '  npm = ' + (npm -v))
`$env:VITE_DEV_BACKEND = 'http://127.0.0.1:$BackendPort'
npm run dev -- --host 0.0.0.0 --port $FrontendPort
"@

Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backendCmd)
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCmd)

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:$FrontendPort"
