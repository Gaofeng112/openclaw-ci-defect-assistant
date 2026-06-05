param(
    [string]$UserId = "u001",
    [Parameter(Mandatory = $true)]
    [string]$ConversationId,
    [Parameter(Mandatory = $true)]
    [string]$Text,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$body = @{
    user_id = $UserId
    conversation_id = $ConversationId
    text = $Text
} | ConvertTo-Json -Compress

$response = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/assistant/chat" `
    -ContentType "application/json; charset=utf-8" `
    -Body $body

$response.reply
