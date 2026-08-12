#!/bin/bash

# 测试新的账号切换 API（无需 base64 编码）
API_BASE="http://10.10.10.50:9987"

echo "=========================================="
echo "测试账号切换 API (无需 base64)"
echo "服务器: $API_BASE"
echo "=========================================="
echo

# 创建测试用的 auth.json
cat > /tmp/test_auth.json << 'EOF'
{
  "sessionToken": "test_token_12345",
  "userId": "user_test_001",
  "expiresAt": "2026-12-31T23:59:59Z"
}
EOF

echo "1. 测试方式 1: 直接传入 auth.json 文件内容"
echo "-------------------------------------------"
curl -X POST "$API_BASE/v1/codex-app/auth" \
  -H "Content-Type: application/json" \
  -d @/tmp/test_auth.json | python3 -m json.tool
echo
echo

echo "2. 测试方式 2: 使用 auth_json 字段包装（对象）"
echo "-------------------------------------------"
curl -X POST "$API_BASE/v1/codex-app/auth" \
  -H "Content-Type: application/json" \
  -d '{
    "auth_json": {
      "sessionToken": "test_token_67890",
      "userId": "user_test_002",
      "expiresAt": "2026-12-31T23:59:59Z"
    }
  }' | python3 -m json.tool
echo
echo

echo "3. 测试方式 3: 使用 auth_json 字段包装（字符串）"
echo "-------------------------------------------"
curl -X POST "$API_BASE/v1/codex-app/auth" \
  -H "Content-Type: application/json" \
  -d '{
    "auth_json": "{\"sessionToken\":\"test_token_abc\",\"userId\":\"user_test_003\"}"
  }' | python3 -m json.tool
echo
echo

echo "4. 测试错误处理: 空 auth_json"
echo "-------------------------------------------"
curl -X POST "$API_BASE/v1/codex-app/auth" \
  -H "Content-Type: application/json" \
  -d '{"auth_json": ""}' | python3 -m json.tool
echo
echo

echo "5. 测试错误处理: 无效的 JSON"
echo "-------------------------------------------"
curl -X POST "$API_BASE/v1/codex-app/auth" \
  -H "Content-Type: application/json" \
  -d '{"auth_json": "not a valid json"}' | python3 -m json.tool
echo
echo

echo "=========================================="
echo "测试完成"
echo "=========================================="
echo
echo "注意："
echo "- 所有测试都使用明文 JSON，无需 base64 编码"
echo "- 实际使用时需要提供真实的 auth.json 内容"
echo "- auth.json 会被写入 ~/.codex/auth.json（默认位置）"

# 清理临时文件
rm -f /tmp/test_auth.json
