#!/bin/bash

# API 测试脚本
# 服务器地址
API_BASE="http://10.10.10.50:9987"

echo "=========================================="
echo "Codex App Remoter API 测试"
echo "服务器: $API_BASE"
echo "=========================================="
echo

# 1. 测试根端点
echo "1. 测试根端点 (GET /)"
curl -s "$API_BASE/" | python3 -m json.tool
echo
echo

# 2. 测试健康检查
echo "2. 测试健康检查 (GET /health)"
curl -s "$API_BASE/health" | python3 -m json.tool
echo
echo

# 3. 测试启动应用（需要认证）
echo "3. 测试启动应用 (POST /v1/codex-app/start)"
echo "注意: 此端点需要 API Key，如果没有设置会返回 401"
curl -s -X POST "$API_BASE/v1/codex-app/start" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
echo
echo

# 4. 测试停止应用（需要认证）
echo "4. 测试停止应用 (POST /v1/codex-app/stop)"
curl -s -X POST "$API_BASE/v1/codex-app/stop" \
  -H "Content-Type: application/json" | python3 -m json.tool
echo
echo

# 5. 测试发送消息（需要认证，需要应用运行）
echo "5. 测试发送消息 (POST /v1/codex-app/messages)"
curl -s -X POST "$API_BASE/v1/codex-app/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, this is a test message",
    "new_chat": true,
    "wait_for_reply": false,
    "timeout_seconds": 60
  }' | python3 -m json.tool
echo
echo

# 6. 测试账号切换（需要认证，需要 base64 编码的 auth.json）
echo "6. 测试账号切换 (POST /v1/codex-app/auth)"
echo "注意: 这需要提供有效的 base64 编码的 auth.json"
echo "示例调用（不执行）:"
echo 'curl -X POST http://10.10.10.50:9987/v1/codex-app/auth \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{"auth_json":"<base64_encoded_auth_json>"}'"'"
echo
echo

echo "=========================================="
echo "测试完成"
echo "=========================================="
echo
echo "总结:"
echo "- 根端点和健康检查应该正常工作"
echo "- 启动/停止/消息/认证端点需要 API Key（如果配置了）"
echo "- 应用路径问题: 需要在 Windows 机器上安装 ChatGPT 或设置正确的路径"
