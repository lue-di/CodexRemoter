@echo off
REM Codex Remoter 启动脚本 - Windows
REM 设置正确的 Codex 应用路径

echo ========================================
echo Codex App Remoter 启动中...
echo ========================================
echo.

REM 设置 Codex 应用路径
set CODEX_APP_PATH=D:\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe

REM 可选：设置 API Key（如果需要）
REM set CODEX_REMOTER_API_KEY=your-secret-key

REM 可选：设置监听端口
set CODEX_REMOTER_PORT=9987

REM 可选：设置监听地址
set CODEX_REMOTER_HOST=0.0.0.0

REM 显示配置
echo 配置信息:
echo   应用路径: %CODEX_APP_PATH%
echo   监听地址: %CODEX_REMOTER_HOST%:%CODEX_REMOTER_PORT%
echo.

REM 检查应用是否存在
if not exist "%CODEX_APP_PATH%" (
    echo [错误] 找不到 Codex 应用: %CODEX_APP_PATH%
    echo 请检查路径是否正确
    pause
    exit /b 1
)

echo [成功] Codex 应用路径正确
echo.
echo 正在启动服务...
echo.

REM 启动服务
python main.py

REM 如果服务退出，暂停以便查看错误
if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败
    pause
)
