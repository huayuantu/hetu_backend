# 多环境部署配置

## 概述

通过 GitHub Secrets 配置环境变量，可以支持部署到多个不同的环境（如生产环境、测试环境、开发环境等）。

## 环境变量配置

### 必需的环境变量

以下环境变量控制三个服务的配置：

#### Alertmanager 配置
- `ALERTMANAGER_WEBHOOK_URL`: Alertmanager webhook 回调地址
  - 生产环境: `http://hetu-api:8000/api/scada/alert/notify`
  - 开发环境: `http://host.docker.internal:18000/api/scada/alert/notify`

#### Prometheus 配置
- `PROMETHEUS_SD_URL`: Prometheus 服务发现 URL
  - 生产环境: `http://hetu-api:8000/api/scada/collector/sd`
  - 开发环境: `http://host.docker.internal:18000/api/scada/collector/sd`

- `PROMETHEUS_PUSHGATEWAY_TARGET`: Pushgateway 目标地址
  - 默认: `hetu-pushgateway:9091`

- `PROMETHEUS_ALERTMANAGER_TARGET`: Alertmanager 目标地址
  - 默认: `hetu-alertmanager:9093`

## GitHub Secrets 配置

### 单环境部署（使用默认值）

如果只部署一个环境，可以不配置这些 Secrets，使用 workflow 中的默认值。

### 多环境部署

#### 方式 1: 使用环境特定的 Secrets（推荐）

在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中，可以为不同环境创建不同的 secrets：

**生产环境 (production)**:
```
ALERTMANAGER_WEBHOOK_URL=http://hetu-api:8000/api/scada/alert/notify
PROMETHEUS_SD_URL=http://hetu-api:8000/api/scada/collector/sd
PROMETHEUS_PUSHGATEWAY_TARGET=hetu-pushgateway:9091
PROMETHEUS_ALERTMANAGER_TARGET=hetu-alertmanager:9093
```

**测试环境 (staging)**:
```
ALERTMANAGER_WEBHOOK_URL=http://hetu-api-staging:8000/api/scada/alert/notify
PROMETHEUS_SD_URL=http://hetu-api-staging:8000/api/scada/collector/sd
PROMETHEUS_PUSHGATEWAY_TARGET=hetu-pushgateway-staging:9091
PROMETHEUS_ALERTMANAGER_TARGET=hetu-alertmanager-staging:9093
```

**开发环境 (development)**:
```
ALERTMANAGER_WEBHOOK_URL=http://host.docker.internal:18000/api/scada/alert/notify
PROMETHEUS_SD_URL=http://host.docker.internal:18000/api/scada/collector/sd
PROMETHEUS_PUSHGATEWAY_TARGET=hetu-pushgateway:9091
PROMETHEUS_ALERTMANAGER_TARGET=hetu-alertmanager:9093
```

#### 方式 2: 修改 Workflow 支持环境选择

可以修改 `.github/workflows/deploy.yml`，添加环境选择功能：

```yaml
jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [production, staging, development]
    steps:
      # ...
      - name: Deploy to ${{ matrix.environment }}
        # 使用环境特定的 secrets
```

## 配置文件生成流程

1. **模板文件**: `*.yml.template` - 包含环境变量占位符
2. **生成脚本**: `scripts/generate-deploy-configs.sh` - 使用 `envsubst` 替换占位符
3. **实际配置**: `*.yml` - 生成的最终配置文件（不提交到 Git）

### 模板文件示例

`deploy/alertmanager/alertmanager.yml.template`:
```yaml
receivers:
  - name: alert_api
    webhook_configs:
      - url: ${ALERTMANAGER_WEBHOOK_URL}
```

`deploy/prometheus/prometheus.yml.template`:
```yaml
http_sd_configs:
  - url: '${PROMETHEUS_SD_URL}'
```

## 部署流程

### 自动部署（CI/CD）

1. 推送 tag: `git tag v1.0.0 && git push origin v1.0.0`
2. GitHub Actions 触发构建
3. 从 GitHub Secrets 读取环境变量（如果配置）
4. 使用环境变量生成配置文件
5. 部署到服务器

### 手动部署

```bash
cd /opt/hetu-backend

# 设置环境变量
export ALERTMANAGER_WEBHOOK_URL="http://hetu-api:8000/api/scada/alert/notify"
export PROMETHEUS_SD_URL="http://hetu-api:8000/api/scada/collector/sd"
export PROMETHEUS_PUSHGATEWAY_TARGET="hetu-pushgateway:9091"
export PROMETHEUS_ALERTMANAGER_TARGET="hetu-alertmanager:9093"

# 生成配置文件
./scripts/generate-deploy-configs.sh

# 部署
export HETU_VERSION=1.0.0
export REGISTRY="crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com"
export IMAGE_NAME="hetu_xinhong/hetu-backend"
docker-compose -f docker-compose.prod.yml up -d
```

## 多环境部署示例

### 场景：生产环境和测试环境

#### 1. 配置 GitHub Secrets

**生产环境 Secrets**:
- `DEPLOY_HOST_PROD`: 生产服务器地址
- `DEPLOY_USER_PROD`: 生产服务器用户
- `DEPLOY_SSH_KEY_PROD`: 生产服务器 SSH 密钥
- `ALERTMANAGER_WEBHOOK_URL_PROD`: 生产环境 webhook URL
- `PROMETHEUS_SD_URL_PROD`: 生产环境 SD URL

**测试环境 Secrets**:
- `DEPLOY_HOST_STAGING`: 测试服务器地址
- `DEPLOY_USER_STAGING`: 测试服务器用户
- `DEPLOY_SSH_KEY_STAGING`: 测试服务器 SSH 密钥
- `ALERTMANAGER_WEBHOOK_URL_STAGING`: 测试环境 webhook URL
- `PROMETHEUS_SD_URL_STAGING`: 测试环境 SD URL

#### 2. 修改 Workflow

创建多个部署 job，每个环境一个：

```yaml
jobs:
  build:
    # 构建镜像...
  
  deploy-production:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    # 使用生产环境 secrets
    
  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/develop'
    # 使用测试环境 secrets
```

## 环境变量优先级

1. **GitHub Secrets** (最高优先级)
2. **Workflow env 变量**
3. **脚本默认值** (最低优先级)

## 注意事项

1. **配置文件不提交**: 生成的 `*.yml` 文件已在 `.gitignore` 中，不会提交到 Git
2. **模板文件提交**: `*.yml.template` 文件需要提交到 Git
3. **环境变量验证**: 脚本会检查必需的环境变量是否设置
4. **envsubst 依赖**: 需要安装 `gettext` 包（包含 `envsubst` 命令）

## 相关文件

- `deploy/alertmanager/alertmanager.yml.template`: Alertmanager 配置模板
- `deploy/prometheus/prometheus.yml.template`: Prometheus 配置模板
- `scripts/generate-deploy-configs.sh`: 配置文件生成脚本
- `.github/workflows/deploy.yml`: CI/CD 工作流配置

