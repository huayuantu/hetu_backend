# API 更新接口问题分析

## 问题描述

`POST /api/scada/updates` 接口在接收请求时出现 `field required` 错误，提示 `["body", "payload"]` 字段缺失。

## 接口定义

```python
@router.post("/updates", response=AppUpdateOut)
@api_schema
def create_update(
    request,
    payload: AppUpdateIn,
    file: UploadedFile | None = File(None),
):
```

## 问题分析

1. **Django Ninja 的标准行为**：当函数参数是 `payload: AppUpdateIn` 时，应该直接发送 JSON 对象，Django Ninja 会自动解析为 `payload` 参数。

2. **文件参数的影响**：由于存在 `file: UploadedFile | None = File(None)` 参数，Django Ninja 可能要求使用 `multipart/form-data` 格式，即使 `file` 为 `None`。

3. **错误信息**：`["body", "payload"]` 字段缺失，说明 Django Ninja 期望请求体包含 `payload` 字段。

## 解决方案

### 方案 1：修改后端接口（推荐）

将 `file` 参数改为可选，并且在没有文件时也支持纯 JSON：

```python
@router.post("/updates", response=AppUpdateOut)
@api_schema
def create_update(
    request,
    payload: AppUpdateIn,
    file: UploadedFile | None = None,  # 移除 File(None)
):
    """创建应用更新版本（公开接口）"""
    # ... 现有代码 ...
```

### 方案 2：使用 multipart/form-data 格式

在 GitHub Actions 中使用 `multipart/form-data` 格式发送请求：

```powershell
$formData = @{
    version = $version
    platform = "windows"
    download_url = $downloadUrl
    signature = "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkK"
    release_notes = "Windows 版本自动构建 - $version"
    is_active = $true
    file_size = [int]$fileSize
    force_update = $false
}

$response = Invoke-RestMethod -Uri $apiUrl -Method Post -Form $formData
```

### 方案 3：创建专门的接口

创建一个新的接口专门用于 GitHub Actions，不需要文件上传功能：

```python
@router.post("/updates/auto", response=AppUpdateOut)
@api_schema
def create_update_auto(
    request,
    payload: AppUpdateIn,
):
    """自动创建应用更新版本（用于 CI/CD，不支持文件上传）"""
    # 复用 create_update 的逻辑，但不处理文件上传
    return create_update(request, payload, file=None)
```

## 当前状态

- GitHub Actions 工作流已修改为直接发送 JSON（不包装 `payload`）
- 需要测试或修改后端接口以支持纯 JSON 请求

## 测试命令

```bash
# 测试直接发送 JSON（当前方式）
curl -X POST "https://app1.xinhong.tech/api/api/scada/updates" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "0.2.0",
    "platform": "windows",
    "download_url": "https://github.com/...",
    "signature": "dW50cnVzdGVk...",
    "release_notes": "Test",
    "is_active": true,
    "file_size": 4428334,
    "force_update": false
  }'
```

