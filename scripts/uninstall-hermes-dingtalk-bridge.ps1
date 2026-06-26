$ErrorActionPreference = "Stop"

$PluginName = "ci-defect-dingtalk-bridge"
$Target = Join-Path $env:LOCALAPPDATA "hermes\plugins\$PluginName"

& hermes plugins disable $PluginName

if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
}

Write-Host "Uninstalled Hermes DingTalk bridge."
Write-Host "DingTalk, Teambition and Jenkins config were not changed."
