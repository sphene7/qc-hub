# Shared conda + nvm helpers for ExcelToWeb (Windows).
$ErrorActionPreference = "Stop"

$EnvName = "excel-to-web"
$NodeVersion = "20.19.0"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Get-CondaBase {
    $info = conda info --base 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $info) {
        throw "未找到 conda。请先安装 Anaconda/Miniconda，并确保 conda 在 PATH 中。"
    }
    return $info.Trim()
}

function Get-EnvPython {
    $base = Get-CondaBase
    $py = Join-Path $base "envs\$EnvName\python.exe"
    if (-not (Test-Path $py)) {
        throw "conda 环境 '$EnvName' 不存在。请先运行: .\setup.ps1"
    }
    return $py
}

function Use-ProjectNode {
    if (-not (Get-Command nvm -ErrorAction SilentlyContinue)) {
        throw "未找到 nvm。请确认 nvm-windows 已安装且在 PATH 中。"
    }
    $current = (node -v 2>$null)
    if ($current -ne "v$NodeVersion") {
        Write-Host "nvm use $NodeVersion"
        nvm use $NodeVersion | Out-Host
    }
    $ver = (node -v 2>$null)
    if ($ver -ne "v$NodeVersion") {
        throw "切换 Node 失败，当前为 '$ver'，期望 v$NodeVersion。可用: nvm install $NodeVersion"
    }
}
