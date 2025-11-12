# 环境变量检查清单

本文档列出了所有需要配置的环境变量，基于实际的 `.env` 文件和代码使用情况。

## 必需的环境变量

### Django 核心配置
- `DEBUG`: Django 调试模式（生产环境应设置为 `False`）
- `SECRET_KEY`: Django 密钥（必须更改，不要使用默认值）
- `UPLOAD_ROOT`: 上传文件目录（默认: `/etc/api/uploads`）
- `ALLOWED_HOSTS`: 允许的主机列表（可选，默认: `*`）

### 数据库配置
- `DATABASE_URL`: 数据库连接 URL
  - 格式: `postgres://user:password@host:port/dbname` 或 `postgresql://...`
  - 示例: `postgres://hetu:hetu@hetu-db:5432/hetu`

### Prometheus 配置
- `PROMETHEUS_URL`: Prometheus 服务地址（默认: `http://hetu-tsdb:9090`）
- `PUSHGATEWAY_URL`: Pushgateway 服务地址（默认: `http://hetu-pushgateway:9091`）
- `PROMETHEUS_RULES_DIR`: Prometheus 规则目录（默认: `/etc/prometheus/include`）

### Supervisor 配置
- `SUPERVISOR_XMLRPC_URL`: Supervisor XML-RPC 接口地址（默认: `http://hetu-collector:9001/RPC2`）
- `SUPERVISOR_COLLECTOR_COMMAND`: Collector 执行命令（格式: `python -m apps.scada.script.collector`）
- `SUPERVISOR_COLLECTOR_ADVERTISE`: Collector 暴露地址（格式: `hetu-collector`，不包含协议和端口）
- `SUPERVISOR_COLLECTOR_DIR`: Collector 配置目录（默认: `/etc/supervisor/include`）

## 可选的环境变量（根据功能需求）

### 萤石云配置（如果使用萤石云视频功能）
- `YS_APPKEY`: 萤石云 AppKey
- `YS_APPSECRET`: 萤石云 AppSecret

### IVM 华为云配置（如果使用华为云视频功能）
- `IVM_BASE_URL`: IVM 基础 URL（默认: `https://api-ivm.myhuaweicloud.com`）
- `IVM_USER_ID`: IVM 用户 ID
- `IVM_ACCESS_KEY`: IVM Access Key
- `IVM_SECRET_KEY`: IVM Secret Key

### 阿里云 OSS 配置（如果使用 OSS 存储功能）
- `OSS_ENDPOINT`: OSS 端点（默认: `oss-cn-shanghai.aliyuncs.com`）
- `OSS_BUCKET_NAME`: OSS 存储桶名称（默认: `hetu-scada`）
- `OSS_ACCESS_KEY_ID`: OSS Access Key ID（必需，用于认证）
- `OSS_ACCESS_KEY_SECRET`: OSS Access Key Secret（必需，用于认证）

**注意**: OSS 认证使用 `EnvironmentVariableCredentialsProvider`，会查找以下环境变量：
- `OSS_ACCESS_KEY_ID` 或 `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `OSS_ACCESS_KEY_SECRET` 或 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`

## 已废弃的环境变量（代码中未使用）

以下环境变量在代码中未使用，可能是历史遗留配置：
- `DJANGO_RUNSERVER`: Django 开发服务器地址（代码中使用 gunicorn，不使用此配置）
- `CACHE_URL`: 缓存配置（代码中硬编码使用内存缓存）

## 环境变量格式说明

### SUPERVISOR_COLLECTOR_COMMAND
- ✅ 正确: `python -m apps.scada.script.collector`
- ❌ 错误: `python /app/src/apps/scada/script/collector.py`

### SUPERVISOR_COLLECTOR_ADVERTISE
- ✅ 正确: `hetu-collector`（仅主机名）
- ❌ 错误: `http://hetu-collector:20000`（包含协议和端口）

### DATABASE_URL
- ✅ 支持: `postgres://user:password@host:port/dbname`
- ✅ 支持: `postgresql://user:password@host:port/dbname`
- 两种格式都可以，`django-environ` 会自动处理

## 检查清单

在部署前，请确认：

- [ ] `SECRET_KEY` 已更改（不是默认值）
- [ ] `DEBUG=False`（生产环境）
- [ ] `DATABASE_URL` 配置正确且可访问
- [ ] 所有必需的环境变量都已设置
- [ ] 如果使用 OSS，已配置 `OSS_ACCESS_KEY_ID` 和 `OSS_ACCESS_KEY_SECRET`
- [ ] 如果使用萤石云，已配置 `YS_APPKEY` 和 `YS_APPSECRET`
- [ ] 如果使用华为云 IVM，已配置所有 IVM 相关变量
- [ ] `SUPERVISOR_COLLECTOR_COMMAND` 使用正确的格式
- [ ] `SUPERVISOR_COLLECTOR_ADVERTISE` 仅包含主机名

## 参考文件

- `env.example`: 环境变量示例文件（包含示例值，用于文档参考和本地开发）
- `env.template`: 环境变量模板文件（包含 `${VAR}` 占位符，用于 CI/CD 自动生成）
- `docs/cicd-setup.md`: CI/CD 配置文档中的环境变量部分
- `config/settings.py`: Django 设置文件，查看实际使用的环境变量

**文件说明**:
- `env.example`: 用于开发者参考，显示需要配置的环境变量及其示例值
- `env.template`: 用于 GitHub Actions 自动生成 `.env` 文件

