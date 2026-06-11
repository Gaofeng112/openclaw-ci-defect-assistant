param(
    [switch]$SkipOpenClawInstall
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "==> Install Python CLI"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\ci-defect-assistant.exe init | Out-Host
.\.venv\Scripts\ci-defect-assistant.exe doctor | Out-Host

Write-Host "==> Validate OpenClaw plugin"
Push-Location "openclaw-plugin"
npm install
npm run plugin:validate
Pop-Location

if (-not $SkipOpenClawInstall) {
    Write-Host "==> Install OpenClaw plugin"
    openclaw plugins install --link .\openclaw-plugin --dangerously-force-unsafe-install
    openclaw gateway restart
    openclaw plugins inspect openclaw-ci-defect-assistant
    openclaw plugins doctor
}

Write-Host "==> Done"
