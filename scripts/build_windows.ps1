param(
    [string]$Version = "0.1.0",
    [switch]$SkipDependencies,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $SkipDependencies) {
    Write-Host "Installing build and runtime dependencies"
    python -m pip install --upgrade pyinstaller
    python -m pip install -r requirements.txt
}

Write-Host "Building dist\Panoptix.exe"
python -m PyInstaller --clean --noconfirm panoptix.spec

$exePath = Join-Path $projectRoot "dist\Panoptix.exe"
if (-not (Test-Path $exePath)) {
    throw "PyInstaller did not produce dist\Panoptix.exe"
}
Write-Host "Built $exePath"

if ($SkipInstaller) {
    return
}

$iscc = (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

if (-not $iscc) {
    Write-Warning "Inno Setup was not found, so only dist\Panoptix.exe was built."
    Write-Warning "Install it with 'winget install JRSoftware.InnoSetup' and run this script again to get the installer."
    return
}

Write-Host "Building the installer with $iscc"
& $iscc "/DAppVersion=$Version" (Join-Path $projectRoot "installer\panoptix.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

Write-Host "Built dist\Panoptix-Setup-$Version.exe"
