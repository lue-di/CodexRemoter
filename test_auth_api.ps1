# Windows PowerShell 测试脚本 - 账号切换 API（无需 base64）
$API_BASE = "http://10.10.10.50:9987"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "测试账号切换 API (无需 base64)" -ForegroundColor Cyan
Write-Host "服务器: $API_BASE" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host

# 创建测试用的 auth.json
$testAuth = @{
    sessionToken = "test_token_12345"
    userId = "user_test_001"
    expiresAt = "2026-12-31T23:59:59Z"
} | ConvertTo-Json

Write-Host "1. 测试方式 1: 直接传入 auth.json 内容" -ForegroundColor Yellow
Write-Host "-------------------------------------------"
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/v1/codex-app/auth" `
        -Method Post `
        -ContentType "application/json" `
        -Body $testAuth
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "错误: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        $_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json
    }
}
Write-Host
Write-Host

Write-Host "2. 测试方式 2: 使用 auth_json 字段包装（对象）" -ForegroundColor Yellow
Write-Host "-------------------------------------------"
$wrappedAuth = @{
    auth_json = @{
        sessionToken = "test_token_67890"
        userId = "user_test_002"
        expiresAt = "2026-12-31T23:59:59Z"
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$API_BASE/v1/codex-app/auth" `
        -Method Post `
        -ContentType "application/json" `
        -Body $wrappedAuth
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "错误: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        $_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json
    }
}
Write-Host
Write-Host

Write-Host "3. 测试方式 3: 使用 auth_json 字段包装（字符串）" -ForegroundColor Yellow
Write-Host "-------------------------------------------"
$authString = @{
    auth_json = '{"sessionToken":"test_token_abc","userId":"user_test_003"}'
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$API_BASE/v1/codex-app/auth" `
        -Method Post `
        -ContentType "application/json" `
        -Body $authString
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "错误: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails) {
        $_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json
    }
}
Write-Host
Write-Host

Write-Host "4. 测试错误处理: 空 auth_json" -ForegroundColor Yellow
Write-Host "-------------------------------------------"
$emptyAuth = @{ auth_json = "" } | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$API_BASE/v1/codex-app/auth" `
        -Method Post `
        -ContentType "application/json" `
        -Body $emptyAuth
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "预期错误: $($_.Exception.Message)" -ForegroundColor Green
    if ($_.ErrorDetails) {
        $_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json
    }
}
Write-Host
Write-Host

Write-Host "5. 测试错误处理: 无效的 JSON" -ForegroundColor Yellow
Write-Host "-------------------------------------------"
$invalidAuth = @{ auth_json = "not a valid json" } | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$API_BASE/v1/codex-app/auth" `
        -Method Post `
        -ContentType "application/json" `
        -Body $invalidAuth
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "预期错误: $($_.Exception.Message)" -ForegroundColor Green
    if ($_.ErrorDetails) {
        $_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json
    }
}
Write-Host
Write-Host

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "测试完成" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host
Write-Host "注意：" -ForegroundColor Yellow
Write-Host "- 所有测试都使用明文 JSON，无需 base64 编码"
Write-Host "- 实际使用时需要提供真实的 auth.json 内容"
Write-Host "- auth.json 会被写入 ~/.codex/auth.json（默认位置）"
