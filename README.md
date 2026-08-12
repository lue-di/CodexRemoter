# Codex App Remoter

这是一个控制 Codex 桌面 App 的本地 REST API。它通过 Chromium DevTools Protocol（CDP）连接 App 的渲染页面，完成：

- 自动启动 ChatGPT/Codex App，并为它分配 loopback 调试端口；
- 找到 Codex composer，输入消息并点击 Send；
- 等待页面上的 assistant 消息完成后返回文本。
- **切换账号：替换 auth.json 并重启应用以生效**

它不调用 `codex exec`，也不启动 `codex app-server`。当前 Codex 桌面 App 的稳定控制入口是 App 的 UI/CDP 注入；UI 选择器属于实现细节，升级 App 后可能需要调整。

## 安装与启动

```bash
python3 -m pip install -e .
python3 main.py
```

### Windows 用户

**自动发现 Codex/ChatGPT 应用：**

服务会自动搜索以下位置：
- `%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe` 和 `Codex.exe`
- `%PROGRAMFILES%\ChatGPT\ChatGPT.exe` 和 `Codex.exe`
- **微软商店安装**：自动扫描所有本地磁盘的 `WindowsApps` 目录
  - 例如：`D:\Program Files\WindowsApps\OpenAI.Codex_*\app\Codex.exe`
- **PATH 中的命令**：`codex.exe` 或 `chatgpt.exe`

**手动指定路径：**

如果自动发现失败，请设置 `CODEX_APP_PATH` 环境变量：

```cmd
# 指向可执行文件
set CODEX_APP_PATH=D:\Program Files\WindowsApps\OpenAI.Codex_1.0.0.0_x64__abc\app\Codex.exe
python main.py

# 或指向包含可执行文件的目录
set CODEX_APP_PATH=D:\Path\To\Codex\app
python main.py
```

或使用 PowerShell：

```powershell
$env:CODEX_APP_PATH="D:\Program Files\WindowsApps\OpenAI.Codex_1.0.0.0_x64__abc\app\Codex.exe"
python main.py
```

**查找微软商店安装的路径：**

```powershell
# 查找 Codex 或 ChatGPT 的安装位置
Get-ChildItem "C:\Program Files\WindowsApps" -Filter "*Codex*" -Directory -ErrorAction SilentlyContinue
Get-ChildItem "D:\Program Files\WindowsApps" -Filter "*Codex*" -Directory -ErrorAction SilentlyContinue
```

### macOS 用户

默认只监听 `127.0.0.1:8000`。如果服务需要被其他机器调用，必须设置 API Key，并自行放在 TLS/反向代理后：

```bash
export CODEX_REMOTER_API_KEY='change-me'
export CODEX_REMOTER_ALLOWED_ROOTS="$HOME/Code"
python3 main.py
```

如果 Codex App 已经是用调试端口启动的，可以复用它：

```bash
export CODEX_DEBUG_PORT=63254
export CODEX_REMOTER_AUTOSTART=false
```

macOS 默认 App 路径是 `/Applications/ChatGPT.app`，也可以设置 `CODEX_APP_PATH`。

**Windows 平台：**
- 默认自动搜索 `%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe` 等常见路径
- auth.json 默认路径：`%APPDATA%\Codex\auth.json` 或 `%APPDATA%\ChatGPT\auth.json`
- 可通过 `CODEX_APP_PATH` 和 `CODEX_REMOTER_AUTH_FILE` 自定义路径

**macOS 平台：**
- 默认路径：`/Applications/ChatGPT.app`
- auth.json 默认路径：`~/Library/Application Support/Codex/auth.json`

如果 macOS 上已有 App 进程且带有 CDP 端口，服务会自动发现并复用；如果已有进程没有 CDP 端口，自动启动会先请求 App 正常退出，再以受控参数重新打开。

传入 `cwd` 时，服务使用桌面 App 自带的官方启动器命令 `codex app PATH` 打开该工作区，再发送消息；可以用 `CODEX_BINARY` 指定启动器路径。

如果需要自定义 auth.json 路径，可以设置 `CODEX_REMOTER_AUTH_FILE` 环境变量：

**Windows:**
```cmd
set CODEX_REMOTER_AUTH_FILE=%APPDATA%\ChatGPT\auth.json
```

**macOS/Linux:**
```bash
export CODEX_REMOTER_AUTH_FILE="$HOME/Library/Application Support/Codex/auth.json"
```

## API 示例

启动 App：

```bash
curl -X POST http://127.0.0.1:8000/v1/codex-app/start \
  -H 'Content-Type: application/json' \
  -d '{}'
```

新开一个 Codex 对话并发送消息：

```bash
curl -X POST http://127.0.0.1:8000/v1/codex-app/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"请分析当前项目结构并给出改进建议","new_chat":true,"wait_for_reply":true}'
```

继续当前页面上的对话：

```bash
curl -X POST http://127.0.0.1:8000/v1/codex-app/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"继续上一个任务，先只检查测试，不要修改文件","new_chat":false}'
```

切换账号（直接传入 auth.json 内容，无需 base64 编码）：

**macOS/Linux:**
```bash
# 方式 1: 直接传入 auth.json 文件内容
curl -X POST http://127.0.0.1:8000/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d @~/your-auth.json

# 方式 2: 使用 auth_json 字段包装
curl -X POST http://127.0.0.1:8000/v1/codex-app/auth \
  -H 'Content-Type: application/json' \
  -d '{"auth_json": {"sessionToken": "...", "userId": "..."}}'
```

**Windows PowerShell:**
```powershell
# 方式 1: 直接读取文件
$authJson = Get-Content "C:\Path\To\auth.json" -Raw
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/codex-app/auth" `
    -Method Post `
    -ContentType "application/json" `
    -Body $authJson

# 方式 2: 使用 auth_json 字段
$authContent = Get-Content "C:\Path\To\auth.json" -Raw | ConvertFrom-Json
$body = @{ auth_json = $authContent } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/codex-app/auth" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

**注意：** 
- **无需 base64 编码**，直接传入 JSON 即可
- 切换账号后，应用会自动重启
- 如果此时有其他请求正在发送消息，它们会自动等待重启完成后再继续执行
- auth.json 默认位置：`~/.codex/auth.json` (所有平台)，可通过 `CODEX_HOME` 或 `CODEX_REMOTER_AUTH_FILE` 环境变量自定义

返回的 `reply` 是页面中最后一条 assistant 消息的文本。`wait_for_reply=false` 时只负责输入并点击发送，接口会立即返回。

## 重要限制

CDP 端口只绑定到 `127.0.0.1`，不要把它或本 API 直接暴露到公网。Codex App 的登录状态沿用当前桌面用户；账号切换 API 会备份并替换 `auth.json`，然后重启应用。自动发送会驱动真实桌面应用，建议在专用用户和受信任工作目录中运行。
