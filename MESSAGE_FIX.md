# 发送消息 API 修复

## 🐛 问题描述

**错误信息：** `找不到 Codex 消息输入框`

**原因：** 
- 单一选择器无法匹配所有可能的 Codex UI 变化
- 页面可能需要时间加载
- Codex 应用的 DOM 结构可能已更新

---

## ✅ 修复方案

### 改进的选择器策略

**修改文件：** `codex_remoter/client.py` - `_prepare_script()` 方法

### 主要改进

#### 1. **多重选择器回退机制**

按优先级尝试多个选择器：
```javascript
// 1. 优先：Codex 特定属性
document.querySelector('[data-codex-composer="true"]')

// 2. 标准：可编辑文本框
document.querySelector('[role="textbox"][contenteditable="true"]')

// 3. 备选：textarea 元素
document.querySelector('textarea[placeholder*="Message"]')
document.querySelector('textarea[placeholder*="消息"]')

// 4. 通用：任何可编辑元素
document.querySelector('[contenteditable="true"][role="textbox"]')
document.querySelector('div[contenteditable="true"]')

// 5. 最后：查找所有可见的可编辑元素
[...document.querySelectorAll('[contenteditable="true"]')]
  .find(el => el.offsetParent !== null)
```

#### 2. **改进的文本插入**

根据元素类型使用不同方法：
```javascript
// textarea 元素
if (box.tagName === 'TEXTAREA') {
  box.value = text;
  box.dispatchEvent(new Event('input', {bubbles:true}));
}
// contenteditable div
else {
  box.innerHTML = '<p dir="auto">' + text + '</p>';
}
```

#### 3. **增强的按钮查找**

支持多语言和多种查找方式：
```javascript
// 1. 英文 aria-label
document.querySelector('button[aria-label="Send"]')

// 2. 中文 aria-label
document.querySelector('button[aria-label="发送"]')

// 3. 模糊匹配
buttons.find(b => /send|发送/i.test(label))
```

#### 4. **增加等待时间**

给页面更多时间加载：
- 新对话点击后：500ms（原 350ms）
- 聚焦后：100ms（新增）
- 输入后：200ms（原 150ms）

#### 5. **更好的错误提示**

```javascript
'找不到 Codex 消息输入框。请确保 Codex 页面已完全加载。'
'Codex 发送按钮不可用或禁用'
```

---

## 📝 改进对比

### 修复前

```javascript
// 单一选择器
const box = document.querySelector('[data-codex-composer="true"]') || 
            document.querySelector('[role="textbox"][contenteditable="true"]');

// 单一按钮查找
const send = document.querySelector('button[aria-label="Send"]');
```

**问题：**
- ❌ UI 变化时立即失败
- ❌ 不支持多语言
- ❌ 没有回退机制

### 修复后

```javascript
// 多重选择器回退
let box = trySelector1() || trySelector2() || ... || findVisibleEditable();

// 多重按钮查找
let send = tryEnglish() || tryChinese() || fuzzyMatch();
```

**优势：**
- ✅ 强大的容错性
- ✅ 支持多语言
- ✅ 多层回退机制
- ✅ 适应 UI 变化

---

## 🧪 测试方法

### 测试 1: 发送消息（不等待回复）

```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, this is a test!",
    "new_chat": true,
    "wait_for_reply": false
  }'
```

**预期成功响应：**
```json
{
    "message": "Hello, this is a test!",
    "reply": "",
    "elapsed_ms": 500,
    "target_id": "...",
    "url": "app://-/index.html"
}
```

### 测试 2: 发送消息（等待回复）

```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Say hello in one word",
    "new_chat": true,
    "wait_for_reply": true,
    "timeout_seconds": 30
  }'
```

**预期成功响应：**
```json
{
    "message": "Say hello in one word",
    "reply": "Hello!",
    "elapsed_ms": 3500,
    "target_id": "...",
    "url": "app://-/index.html"
}
```

---

## 🔧 故障排查

### 如果仍然失败

**检查 1: Codex 页面是否打开**
```bash
curl -s http://10.10.10.50:9987/health | grep -A 5 targets
```

应该看到至少一个 target：
```json
"targets": [
    {"id": "...", "title": "Codex", "url": "app://-/index.html"}
]
```

**检查 2: 是否在定价页面**

如果看到 `"url": "https://chatgpt.com/?source=codex#pricing"`，需要关闭该页面或切换到主页面。

**检查 3: 手动测试选择器**

在 Codex 开发者工具中运行：
```javascript
// 测试输入框
document.querySelector('[data-codex-composer="true"]')
document.querySelector('[role="textbox"][contenteditable="true"]')
document.querySelectorAll('[contenteditable="true"]')

// 测试发送按钮
document.querySelector('button[aria-label="Send"]')
[...document.querySelectorAll('button')].filter(b => 
  /send/i.test(b.getAttribute('aria-label') || b.innerText)
)
```

---

## 📦 部署步骤

1. **停止服务**
```cmd
taskkill /F /IM python.exe
```

2. **替换文件**
- 更新 `codex_remoter/client.py`

3. **启动服务**
```cmd
cd D:\Users\DELL\Desktop\xh
start_windows.bat
```

4. **测试验证**
```bash
curl -X POST http://10.10.10.50:9987/v1/codex-app/messages \
  -H "Content-Type: application/json" \
  -d '{"message":"test","new_chat":true,"wait_for_reply":false}'
```

---

## ✅ 改进总结

| 特性 | 修复前 | 修复后 |
|------|--------|--------|
| 选择器数量 | 2 个 | 7+ 个 |
| 回退机制 | 无 | 多层 |
| 多语言支持 | 仅英文 | 中英文 |
| 容错性 | 弱 | 强 |
| 等待时间 | 固定 | 优化 |
| 错误提示 | 简单 | 详细 |

---

## 🎯 预期结果

修复后应该能够：
- ✅ 找到各种版本的 Codex 输入框
- ✅ 支持 textarea 和 contenteditable 两种类型
- ✅ 适应 UI 更新和变化
- ✅ 提供清晰的错误信息
- ✅ 支持中英文界面

---

**修复完成，可以部署测试！** 🚀
