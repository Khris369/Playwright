param(
    [string]$Python = "venv\Scripts\python.exe",
    [string]$OutputDir = "dist\picker-agent"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable not found: $Python"
}

& $Python -m pip install --upgrade pyinstaller
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name workflow-picker-agent `
    --distpath $OutputDir `
    --workpath "build\picker-agent" `
    --specpath "build\picker-agent" `
    --collect-all playwright `
    "picker_agent\entrypoint.py"

Write-Host "Built $OutputDir\workflow-picker-agent"
Write-Host "Install Chromium on the target computer with:"
Write-Host "  python -m playwright install chromium"
