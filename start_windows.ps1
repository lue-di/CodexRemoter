# Codex Remoter 启动脚本 - Windows PowerShell

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Codex App Remoter 启动中..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host

# 设置 Codex 应用路径
$env:CODEX_APP_PATH = "D:\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe"

# 可选：设置 API Key（如果需要）
# $env:CODEX_REMOTER_API_KEY = "your-secret-key"

# 可选：设置监听端口
$env:CODEX_REMOTER_PORT = "9987"

# 可选：设置监听地址
$env:CODEX_REMOTER_HOST = "0.0.0.0"

# 显示配置
Write-Host "配置信息:" -ForegroundColor Yellow
Write-Host "  应用路径: $env:CODEX_APP_PATH"
Write-Host "  监听地址: $env:CODEX_REMOTER_HOST`:$env:CODEX_REMOTER_PORT"
Write-Host

# 检查应用是否存在
if (-not (Test-Path $env:CODEX_APP_PATH)) {
    Write-Host "[错误] 找不到 Codex 应用: $env:CODEX_APP_PATH" -ForegroundColor Red
    Write-Host "请检查路径是否正确" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "[成功] Codex 应用路径正确" -ForegroundColor Green
Write-Host
Write-Host "正在启动服务..." -ForegroundColor Yellow
Write-Host

# 启动服务
try {
    python main.py
} catch {
    Write-Host ""
    Write-Host "[错误] 服务启动失败: $_" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
