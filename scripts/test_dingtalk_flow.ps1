$ErrorActionPreference = "Stop"

$baseUrl = $env:CI_ASSISTANT_URL
if (-not $baseUrl) {
    $baseUrl = "http://127.0.0.1:8000"
}

Write-Host "Testing CI assistant at $baseUrl"

$firstBody = @{
    user_id = "u001"
    conversation_id = "ding-local-test"
    text = "ci_test env test branch main"
} | ConvertTo-Json -Compress

$first = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/assistant/chat" `
    -ContentType "application/json; charset=utf-8" `
    -Body $firstBody

Write-Host "First reply:"
$first.reply

if (-not $first.needs_confirmation) {
    throw "Expected needs_confirmation=true before Jenkins trigger."
}

$confirmBody = @{
    user_id = "u001"
    conversation_id = "ding-local-test"
    text = "confirm"
} | ConvertTo-Json -Compress

Write-Host ""
Write-Host "Ready to trigger real Jenkins."
Write-Host "Run the following manually when you want to trigger:"
Write-Host "Invoke-RestMethod -Method Post -Uri '$baseUrl/assistant/chat' -ContentType 'application/json; charset=utf-8' -Body '$confirmBody'"
