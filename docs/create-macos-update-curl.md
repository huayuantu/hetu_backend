# 使用 curl 创建 macOS 版本更新

## 基本命令格式

```bash
curl -X POST "http://localhost:8000/api/scada/updates" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.0",
    "platform": "macos",
    "download_url": "https://example.com/releases/v1.0.0/app.dmg",
    "signature": "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkK",
    "release_notes": "macOS 版本更新说明\n\n- 修复了某些bug\n- 新增了某些功能",
    "file_size": 52428800,
    "is_active": true,
    "force_update": false
  }'
```

## 完整示例（带认证）

如果 API 需要认证，添加 Authorization header：

```bash
curl -X POST "http://localhost:8000/api/scada/updates" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -d '{
    "version": "1.0.0",
    "platform": "macos",
    "download_url": "https://example.com/releases/v1.0.0/app.dmg",
    "signature": "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkK",
    "release_notes": "macOS 版本更新说明\n\n- 修复了某些bug\n- 新增了某些功能",
    "file_size": 52428800,
    "is_active": true,
    "force_update": false
  }'
```

## 使用变量（推荐）

```bash
# 设置变量
API_BASE_URL="http://localhost:8000/api"
VERSION="1.0.0"
DOWNLOAD_URL="https://example.com/releases/v1.0.0/app.dmg"
SIGNATURE="dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkK"
FILE_SIZE=52428800
RELEASE_NOTES="macOS 版本更新说明

- 修复了某些bug
- 新增了某些功能"

# 执行请求
curl -X POST "${API_BASE_URL}/scada/updates" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"${VERSION}\",
    \"platform\": \"macos\",
    \"download_url\": \"${DOWNLOAD_URL}\",
    \"signature\": \"${SIGNATURE}\",
    \"release_notes\": \"${RELEASE_NOTES}\",
    \"file_size\": ${FILE_SIZE},
    \"is_active\": true,
    \"force_update\": false
  }"
```

## 使用 JSON 文件（推荐用于复杂场景）

创建 `update.json` 文件：

```json
{
  "version": "1.0.0",
  "platform": "macos",
  "download_url": "https://example.com/releases/v1.0.0/app.dmg",
  "signature": "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkK",
  "release_notes": "macOS 版本更新说明\n\n- 修复了某些bug\n- 新增了某些功能",
  "file_size": 52428800,
  "is_active": true,
  "force_update": false
}
```

然后使用：

```bash
curl -X POST "http://localhost:8000/api/scada/updates" \
  -H "Content-Type: application/json" \
  -d @update.json
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | ✅ | 版本号，格式：major.minor.patch (例如: 1.0.0) |
| `platform` | string | ✅ | 平台类型，固定值：`macos` |
| `download_url` | string | ✅ | 下载地址（OSS URL 或 CDN URL） |
| `signature` | string | ✅ | Tauri 签名（base64 编码） |
| `release_notes` | string | ❌ | 更新说明/发布日志（默认：空字符串） |
| `file_size` | integer | ❌ | 文件大小（字节，默认：0） |
| `is_active` | boolean | ❌ | 是否激活（默认：true） |
| `force_update` | boolean | ❌ | 是否强制更新（默认：false） |
| `min_version` | string | ❌ | 最低支持版本（可选） |

## 获取 Tauri 签名

签名可以通过以下方式获取：

1. **从构建产物中获取**：
   ```bash
   # macOS 构建后，签名文件通常在：
   # src-tauri/target/release/bundle/macos/*.app.tar.gz.sig
   cat src-tauri/target/release/bundle/macos/*.app.tar.gz.sig
   ```

2. **使用默认签名**（仅用于测试）：
   ```
   dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkK
   ```

## 获取文件大小

```bash
# macOS/Linux
FILE_SIZE=$(stat -f%z "path/to/app.dmg")  # macOS
# 或
FILE_SIZE=$(stat -c%s "path/to/app.dmg")  # Linux

# 在 curl 命令中使用
curl ... -d "{
  ...
  \"file_size\": ${FILE_SIZE},
  ...
}"
```

## 验证更新是否创建成功

```bash
# 查看所有 macOS 更新
curl "http://localhost:8000/api/scada/updates?platform=macos"

# 查看特定版本
curl "http://localhost:8000/api/scada/updates/check?version=0.9.0&platform=macos"
```

## 错误处理

如果版本已存在，会返回 400 错误：
```json
{
  "detail": "Version 1.0.0 for macos already exists"
}
```

## 实际使用示例

```bash
#!/bin/bash

# 配置
API_BASE_URL="http://localhost:8000/api"
VERSION="1.2.3"
DMG_PATH="./dist/hetu-scada-client_1.2.3_aarch64.dmg"
SIGNATURE_PATH="./dist/hetu-scada-client_1.2.3_aarch64.dmg.sig"

# 检查文件是否存在
if [ ! -f "$DMG_PATH" ]; then
  echo "错误: DMG 文件不存在: $DMG_PATH"
  exit 1
fi

if [ ! -f "$SIGNATURE_PATH" ]; then
  echo "错误: 签名文件不存在: $SIGNATURE_PATH"
  exit 1
fi

# 读取签名
SIGNATURE=$(cat "$SIGNATURE_PATH" | tr -d '\n')

# 获取文件大小
FILE_SIZE=$(stat -f%z "$DMG_PATH")

# 构建更新说明
RELEASE_NOTES="macOS 版本 $VERSION

- 修复了某些bug
- 新增了某些功能
- 性能优化"

# 发送请求
curl -X POST "${API_BASE_URL}/scada/updates" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"${VERSION}\",
    \"platform\": \"macos\",
    \"download_url\": \"https://your-cdn.com/releases/${VERSION}/$(basename $DMG_PATH)\",
    \"signature\": \"${SIGNATURE}\",
    \"release_notes\": \"${RELEASE_NOTES}\",
    \"file_size\": ${FILE_SIZE},
    \"is_active\": true,
    \"force_update\": false
  }" | python3 -m json.tool
```

