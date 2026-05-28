$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

python -m PyInstaller --clean --noconfirm panoptix.spec

Write-Host "Built dist\Panoptix.exe"
