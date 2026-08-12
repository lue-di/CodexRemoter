# 部署前检查清单 ✅

## 代码状态
- ✅ 所有 Python 文件编译通过
- ✅ 语法检查无错误
- ✅ 方法完整性验证通过
  - `_macos_main_processes()` ✓
  - `_quit_uninstrumented_macos_app()` ✓
  - `_quit_uninstrumented_windows_app()` ✓
  - `_resolve_app_executable()` ✓
  - `_windows_app_search_paths()` ✓
  - `_serialize_auth()` ✓
  - `_restrict_permissions()` ✓
  - `_auth_file_candidates()` ✓
  - `_resolve_auth_file()` ✓

## 修复的问题
- ✅ 修复 `AttributeError: '_macos_main_processes'` 不存在
- ✅ 修复方法结构错误（代码混在一起）
- ✅ 添加缺失的 macOS 退出方法

## 准备部署到 Windows 服务器

### 1. 同步代码
```bash
# 从本地复制到服务器
scp -r codex_remoter/ user@10.10.10.50:/path/to/project/
```

### 2. 重启服务
在 Windows 服务器上执行：
```cmd
# 停止旧服务
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *main.py*"

# 启动新服务
cd D:\Users\DELL\Desktop\xh
python main.py
```

### 3. 验证启动
```bash
# 从你的机器测试
curl http://10.10.10.50:9987/health | python3 -m json.tool
```

### 4. 预期结果

**成功情况：**
```json
{
    "ok": true,
    "codex_app": {
        "running": true,
        "app_path": "D:\\Program Files\\WindowsApps\\...\\Codex.exe",
        "debug_port": 12480,
        "targets": [...]
    }
}
```

**应用未找到（需要设置路径）：**
```json
{
    "ok": false,
    "codex_app": {
        "running": false,
        "last_error": "找不到 Codex/ChatGPT 应用..."
    }
}
```

## Windows 服务器配置建议

### 如果自动发现失败

1. **查找 Codex 安装位置：**
```powershell
# 搜索 WindowsApps
Get-ChildItem "D:\Program Files\WindowsApps" -Filter "*Codex*" -Directory -ErrorAction SilentlyContinue

# 或搜索可执行文件
Get-ChildItem "D:\Program Files\WindowsApps" -Recurse -Filter "Codex.exe" -ErrorAction SilentlyContinue
```

2. **设置环境变量：**
```cmd
set CODEX_APP_PATH=D:\Program Files\WindowsApps\OpenAI.Codex_xxx\app\Codex.exe
```

3. **或者在启动脚本中设置：**
```cmd
@echo off
set CODEX_APP_PATH=D:\Program Files\WindowsApps\OpenAI.Codex_xxx\app\Codex.exe
set CODEX_REMOTER_API_KEY=your-secret-key
set CODEX_REMOTER_PORT=9987
python main.py
```

## 测试 API

### 1. 健康检查
```bash
curl http://10.10.10.50:9987/health
```

### 2. 启动应用
```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/start \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### 3. 测试账号切换（使用真实 auth.json）
```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d @/path/to/real/auth.json
```

### 4. 发送消息
```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/messages \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Hello from API test",
    "new_chat": true,
    "wait_for_reply": true
  }'
```

## 常见问题

### Q: 服务启动失败
**A:** 检查错误日志，通常是路径问题。使用上面的 PowerShell 命令找到实际路径。

### Q: 找不到应用
**A:** 设置 `CODEX_APP_PATH` 环境变量指向完整的 .exe 路径。

### Q: 启动超时
**A:** 检查防火墙是否阻止了调试端口（默认随机分配）。

### Q: 账号切换失败
**A:** 确保 auth.json 格式正确，路径可写（通常是 `C:\Users\DELL\.codex\auth.json`）。

---

**所有代码已就绪，可以部署！** 🚀
