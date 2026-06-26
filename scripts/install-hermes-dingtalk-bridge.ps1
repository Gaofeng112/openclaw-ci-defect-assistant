$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PluginName = "ci-defect-dingtalk-bridge"
$Source = Join-Path $RepoRoot "hermes-dingtalk-bridge"
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$Target = Join-Path $HermesHome "plugins\$PluginName"

if (!(Test-Path $Source)) {
    throw "Plugin source not found: $Source"
}

New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
}
Copy-Item -Recurse $Source $Target

$HermesExe = (Get-Command hermes).Source
$HermesPython = Join-Path (Split-Path $HermesExe) "python.exe"
if (!(Test-Path $HermesPython)) {
    $HermesPython = "python"
}
& $HermesPython -m pip install "dingtalk-stream>=0.20" httpx | Out-Host

$EnvPath = (& hermes config env-path).Trim()
if (!(Test-Path $EnvPath)) {
    New-Item -ItemType File -Force -Path $EnvPath | Out-Null
}

$content = Get-Content -Raw -Encoding UTF8 $EnvPath
if ($content -match "(?m)^CI_DEFECT_ASSISTANT_ROOT=") {
    $content = $content -replace "(?m)^CI_DEFECT_ASSISTANT_ROOT=.*$", "CI_DEFECT_ASSISTANT_ROOT=$RepoRoot"
} else {
    if ($content.Length -gt 0 -and !$content.EndsWith("`n")) { $content += "`n" }
    $content += "CI_DEFECT_ASSISTANT_ROOT=$RepoRoot`n"
}
Set-Content -Encoding UTF8 -Path $EnvPath -Value $content

& hermes plugins enable $PluginName

foreach ($key in @("DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET", "DINGTALK_ROBOT_CODE")) {
    if ($content -notmatch "(?m)^$key=") {
        Write-Warning "Hermes .env missing $key"
    }
}

Write-Host "Installed Hermes DingTalk bridge: $Target"
Write-Host "Hermes env: $EnvPath"
Write-Host "Restart gateway: hermes gateway run --replace"
