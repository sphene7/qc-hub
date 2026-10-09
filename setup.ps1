# Create conda env + pin Node via nvm, then install Python/JS deps.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. "$PSScriptRoot\scripts\env.ps1"

Write-Host "==> conda 环境: $EnvName"
$base = Get-CondaBase
$envDir = Join-Path $base "envs\$EnvName"
if (Test-Path $envDir) {
    Write-Host "环境已存在，按 environment.yml 更新依赖..."
    conda env update -n $EnvName -f "$PSScriptRoot\environment.yml" --prune
} else {
    Write-Host "正在创建环境（python 3.12）..."
    conda env create -f "$PSScriptRoot\environment.yml"
}

$py = Get-EnvPython
Write-Host "Python: $(& $py --version)"

Write-Host "==> nvm 使用 Node $NodeVersion"
if (-not (Get-Command nvm -ErrorAction SilentlyContinue)) {
    throw "未找到 nvm。请先安装 nvm-windows。"
}
$installed = nvm list
if ($installed -notmatch [regex]::Escape($NodeVersion)) {
    Write-Host "未安装 Node $NodeVersion，开始 nvm install..."
    nvm install $NodeVersion
}
Use-ProjectNode
Write-Host "Node: $(node -v)  npm: $(npm -v)"

Write-Host "==> npm install (frontend)"
npm install --prefix "$PSScriptRoot\frontend"

Write-Host ""
Write-Host "环境就绪。启动: .\start.ps1"
Write-Host "  conda env : $EnvName"
Write-Host "  python    : $py"
Write-Host "  node      : v$NodeVersion (nvm)"
