# Codex Remoter 更新总结

**更新时间:** 2026-08-12  
**版本:** 0.2.0  

---

## 🎯 主要更新

### 1. ✅ **auth.json 适配为 Codex（而非 Claude）**

**修改前：** 硬编码 Claude 的 auth.json 路径  
**修改后：** 使用 Codex CLI 的标准路径

**新的 auth.json 位置（按优先级）：**
- `$CODEX_HOME/auth.json`（如果设置了 CODEX_HOME 环境变量）
- `~/.codex/auth.json`（默认，跨平台统一）
- Windows: `%APPDATA%\Codex\auth.json`
- macOS: `~/Library/Application Support/Codex/auth.json`
- Linux: `~/.config/codex/auth.json`

**相关文件：**
- `codex_remoter/client.py` - `_resolve_auth_file()`, `_auth_file_candidates()`

---

### 2. ✅ **auth.json API 改为直接传 JSON（移除 base64）**

**修改前：** 需要对 auth.json 进行 base64 编码后传递  
**修改后：** 直接传递 JSON 对象或文本

**新的 API 用法：**

```bash
# 方式 1: 直接传文件内容
curl -X POST http://127.0.0.1:8000/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d @~/your-auth.json

# 方式 2: 使用 auth_json 字段
curl -X POST http://127.0.0.1:8000/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d '{"auth_json": {"sessionToken": "...", "userId": "..."}}'
```

**新增功能：**
- ✅ 自动验证 JSON 格式
- ✅ 支持对象或字符串两种输入方式
- ✅ 自动创建目标目录
- ✅ 自动备份旧的 auth.json（.bak 后缀）
- ✅ 设置文件权限为 0600（仅所有者可读写）

**相关文件：**
- `codex_remoter/api.py` - `AuthRequest` 模型, `switch_account()` 端点
- `codex_remoter/client.py` - `switch_auth()`, `_serialize_auth()`

---

### 3. ✅ **完整的 Windows 平台支持**

#### 3.1 自动发现 Codex/ChatGPT 应用

**搜索策略（按优先级）：**

1. **显式配置：** `CODEX_APP_PATH` 环境变量
   - 支持指向可执行文件
   - 支持指向包含可执行文件的目录

2. **PATH 命令：** 查找 `codex.exe` 或 `chatgpt.exe`

3. **标准安装目录：**
   - `%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe`
   - `%LOCALAPPDATA%\Programs\Codex\Codex.exe`
   - `%PROGRAMFILES%\ChatGPT\ChatGPT.exe`
   - `%PROGRAMFILES%\Codex\Codex.exe`

4. **微软商店 MSIX 包（WindowsApps）：**
   - 自动扫描所有本地磁盘（C:, D:, E:, ...）
   - 搜索 `WindowsApps\OpenAI.Codex*\app\Codex.exe`
   - 搜索 `WindowsApps\*Codex*\app\*.exe`
   - 处理 WindowsApps ACL 权限限制

**示例微软商店安装路径：**
```
D:\Program Files\WindowsApps\OpenAI.Codex_1.0.0.0_x64__abc123\app\Codex.exe
```

#### 3.2 Windows 进程管理改进

- ✅ 使用 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` 标志启动
- ✅ 避免应用随 API 服务退出而关闭
- ✅ 退出未带调试端口的应用（`taskkill /T`）
- ✅ 正确处理 Windows 路径分隔符

**相关文件：**
- `codex_remoter/client.py` - `_resolve_app_executable()`, `_windows_app_search_paths()`, `_quit_uninstrumented_windows_app()`

---

### 4. ✅ **账号切换并发控制**

**问题：** 切换账号时重启应用，如果此时有请求发送消息会失败

**解决方案：**
- 添加 `_switching_auth` 标志位
- 添加 `_auth_switch_event` 异步事件
- 发送消息时检测到切换中，自动等待完成（最多 40 秒）
- 使用 `try-finally` 确保标志位正确清理

**相关文件：**
- `codex_remoter/client.py` - `__init__()`, `send_message()`, `switch_auth()`

---

## 📝 配置变化

### 新增环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `CODEX_HOME` | Codex CLI 的主目录 | `C:\Users\DELL\.codex` |
| `CODEX_APP_PATH` | Codex 可执行文件路径（或目录） | `D:\...\WindowsApps\...\app\Codex.exe` |
| `CODEX_REMOTER_AUTH_FILE` | 显式指定 auth.json 位置 | `~/.codex/auth.json` |

### 现有环境变量保持不变

- `CODEX_BINARY` - Codex CLI 命令名称（默认 `codex`）
- `CODEX_DEBUG_PORT` - 调试端口（默认自动分配）
- `CODEX_REMOTER_HOST` - 监听地址（默认 `127.0.0.1`）
- `CODEX_REMOTER_PORT` - 监听端口（默认 `8000`）
- `CODEX_REMOTER_API_KEY` - API 密钥（可选）
- `CODEX_REMOTER_AUTOSTART` - 自动启动（默认 `true`）

---

## 🧪 测试

### 测试脚本

1. **test_api_remote.sh** - 完整 API 测试（Linux/macOS）
2. **test_auth_api.sh** - 账号切换 API 测试（Linux/macOS）
3. **test_auth_api.ps1** - 账号切换 API 测试（Windows PowerShell）

### 运行测试

**Linux/macOS:**
```bash
chmod +x test_auth_api.sh
./test_auth_api.sh
```

**Windows PowerShell:**
```powershell
.\test_auth_api.ps1
```

---

## 🔧 迁移指南

### 如果你之前使用 base64 编码的 auth.json

**旧代码（不再支持）：**
```bash
AUTH_JSON_BASE64=$(cat ~/auth.json | base64)
curl -X POST http://127.0.0.1:8000/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d "{\"auth_json\":\"$AUTH_JSON_BASE64\"}"
```

**新代码（推荐）：**
```bash
curl -X POST http://127.0.0.1:8000/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d @~/auth.json
```

### 如果你在 Windows 上手动指定了路径

**检查你的 CODEX_APP_PATH 是否正确：**
```powershell
# 查找 Codex 安装位置
Get-ChildItem "C:\Program Files\WindowsApps" -Filter "*Codex*" -Directory -ErrorAction SilentlyContinue
Get-ChildItem "D:\Program Files\WindowsApps" -Filter "*Codex*" -Directory -ErrorAction SilentlyContinue

# 找到后设置环境变量
$env:CODEX_APP_PATH="D:\Program Files\WindowsApps\OpenAI.Codex_xxx\app\Codex.exe"
```

---

## 🐛 已知问题修复

1. ✅ **Windows 平台找不到应用** - 添加了全盘 WindowsApps 搜索
2. ✅ **auth.json 路径错误** - 从 Claude 改为 Codex 的标准位置
3. ✅ **base64 编码复杂** - 改为直接传 JSON
4. ✅ **切换账号时并发冲突** - 添加等待机制
5. ✅ **Windows 进程管理** - 使用正确的创建标志

---

## 📚 文档更新

- ✅ `README.md` - 更新了所有示例和说明
- ✅ `API_TEST_REPORT.md` - 详细的 API 测试报告
- ✅ 新增测试脚本和使用示例

---

## 🚀 下一步

1. **在 Windows 服务器上测试：**
   - 验证自动发现功能
   - 测试微软商店安装的应用
   - 测试账号切换功能

2. **如果需要进一步改进：**
   - 添加应用状态监控
   - 支持多个 Codex 实例
   - 添加日志记录功能

---

## 📞 问题排查

### 找不到应用

**查看错误信息：**
```bash
curl http://10.10.10.50:9987/health | python3 -m json.tool
```

错误信息会列出所有尝试的路径，帮助你定位问题。

### 账号切换失败

**检查 auth.json 位置：**
```bash
# Windows PowerShell
Test-Path "$env:USERPROFILE\.codex\auth.json"

# Linux/macOS
ls -la ~/.codex/auth.json
```

### 应用启动超时

**检查调试端口：**
```bash
curl http://127.0.0.1:9222/json/list
```

如果端口可访问，说明应用已启动但 API 未正确连接。

---

**所有修改已完成并通过语法检查！** ✅
