# 一键从母系统导出三项目并写入 deploy 配置（在母系统 ExcelToWeb 根目录运行）
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Wids,

    [string]$SystemName = "XXX管理系统",
    [string]$SystemSubtitle = "产线巡检 · 客诉跟进 · 产品抽检"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Backend = Join-Path $Root "backend"
$Deploy = Join-Path $Root "deploy"
$DataDir = Join-Path $Deploy "data"
$Bundle = Join-Path $DataDir "bundle.json"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

$widArg = ($Wids -join ",")
Write-Host "==> 导出 wid: $widArg"

Push-Location $Backend
try {
    python scripts/export_bundle.py --wids $widArg -o $Bundle
} finally {
    Pop-Location
}

$labels = @("产线巡检", "客诉跟进", "产品抽检")
$keys = @("inspection", "complaint", "sampling")
$modules = @()
for ($i = 0; $i -lt [Math]::Min($Wids.Count, 3); $i++) {
    $modules += @{
        key = $keys[$i]
        label = $labels[$i]
        description = "模块 $($i + 1)"
        project_id = $Wids[$i]
    }
}

$config = @{
    system_name = $SystemName
    system_subtitle = $SystemSubtitle
    modules = $modules
}

$configPath = Join-Path $Deploy "product.modules.json"
$config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8

Write-Host "==> 已写入 $Bundle"
Write-Host "==> 已写入 $configPath"
Write-Host ""
Write-Host "下一步:"
Write-Host "  1. git clone 此仓库为独立 XXX管理系统"
Write-Host "  2. 复制 deploy/.env.example -> deploy/.env"
Write-Host "  3. cd deploy && docker compose up -d --build"
