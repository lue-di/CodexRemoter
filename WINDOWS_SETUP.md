# Windows 服务器快速配置指南

## 🎯 您的 Codex 路径

```
D:\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe
```

## 🚀 快速启动（推荐）

### 方式 1: 使用启动脚本（最简单）

**CMD:**
```cmd
cd D:\Users\DELL\Desktop\xh
start_windows.bat
```

**PowerShell:**
```powershell
cd D:\Users\DELL\Desktop\xh
.\start_windows.ps1
```

启动脚本已经配置好正确的路径，直接运行即可！

---

### 方式 2: 手动设置环境变量

**临时设置（当前会话）:**
```cmd
set CODEX_APP_PATH=D:\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe
set CODEX_REMOTER_PORT=9987
python main.py
```

**永久设置（推荐）:**
```cmd
setx CODEX_APP_PATH "D:\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe"
setx CODEX_REMOTER_PORT "9987"

REM 重启命令提示符后运行
python main.py
```

---

## ✅ 验证配置

启动服务后，从另一台机器测试：

```bash
# 健康检查
curl http://10.10.10.50:9987/health | python3 -m json.tool
```

**成功的响应应该显示：**
```json
{
    "ok": true,
    "codex_app": {
        "running": true,
        "app_path": "D:\\WindowsApps\\OpenAI.Codex_...\\app\\ChatGPT.exe",
        "targets": [...]
    }
}
```

---

## 🧪 测试 API

### 1. 启动应用
```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/start \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 2. 账号切换（无需 base64）
```bash
# 直接传 JSON
curl -X POST http://10.10.10.50:9987/v1/codex-app/auth \
  -H "Content-Type: application/json" \
  -d '{"sessionToken":"xxx","userId":"yyy"}'
```

### 3. 发送消息
```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello from API!",
    "new_chat": true,
    "wait_for_reply": true
  }'
```

---

## 🔧 故障排查

### 问题 1: 启动超时

**检查应用是否存在：**
```powershell
Test-Path "D:\WindowsApps\OpenAI.Codex_26.803.10989.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe"
```

如果返回 `False`，说明路径错误或应用已更新，需要重新查找：
```powershell
Get-ChildItem "D:\WindowsApps" -Filter "*Codex*" -Directory
```

### 问题 2: 端口被占用

```powershell
# 查看端口占用
netstat -ano | findstr :9987

# 如果被占用，更换端口
set CODEX_REMOTER_PORT=9988
```

### 问题 3: 防火墙阻止

```powershell
# 添加防火墙规则（以管理员身份运行）
New-NetFirewallRule -DisplayName "Codex Remoter" -Direction Inbound -Protocol TCP -LocalPort 9987 -Action Allow
```

---

## 📝 配置文件位置

### auth.json 位置
```
C:\Users\DELL\.codex\auth.json
```

### 环境变量
- `CODEX_APP_PATH` - 应用路径（必需）
- `CODEX_REMOTER_PORT` - 监听端口（默认 8000）
- `CODEX_REMOTER_HOST` - 监听地址（默认 127.0.0.1）
- `CODEX_REMOTER_API_KEY` - API 密钥（可选）

---

## 🎉 部署步骤总结

1. ✅ 将 `start_windows.bat` 或 `start_windows.ps1` 复制到项目目录
2. ✅ 双击运行启动脚本
3. ✅ 验证服务启动成功（查看输出）
4. ✅ 从远程测试 API（curl 健康检查）
5. ✅ 完成！

---

**注意：** 如果 Codex 应用更新到新版本，路径中的版本号会变化，需要重新设置。建议使用启动脚本统一管理配置。
