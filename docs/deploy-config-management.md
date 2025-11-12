# 部署配置文件管理（已更新）

## ⚠️ 重要更新

配置文件管理方式已更新为**基于环境变量的模板生成方式**，支持多环境部署。

**新方式**:
- 使用模板文件（`*.yml.template`）和环境变量生成配置文件
- 通过 GitHub Secrets 配置不同环境的环境变量
- 支持部署到多个环境（生产、测试、开发等）

**旧方式**（已废弃）:
- 使用 `*.default.yml` 文件复制

## 新的配置文件管理方式

### 1. 模板文件

模板文件包含环境变量占位符，会提交到 Git：

- `deploy/alertmanager/alertmanager.yml.template`
- `deploy/prometheus/prometheus.yml.template`
- `deploy/supervisor/supervisord.default.conf` (Supervisor 配置不需要环境变量)

### 2. 环境变量

通过环境变量控制配置：

- `ALERTMANAGER_WEBHOOK_URL`: Alertmanager webhook 地址
- `PROMETHEUS_SD_URL`: Prometheus 服务发现 URL
- `PROMETHEUS_PUSHGATEWAY_TARGET`: Pushgateway 目标
- `PROMETHEUS_ALERTMANAGER_TARGET`: Alertmanager 目标

### 3. 生成脚本

使用 `scripts/generate-deploy-configs.sh` 从模板生成配置文件：

```bash
export ALERTMANAGER_WEBHOOK_URL="http://hetu-api:8000/api/scada/alert/notify"
export PROMETHEUS_SD_URL="http://hetu-api:8000/api/scada/collector/sd"
export PROMETHEUS_PUSHGATEWAY_TARGET="hetu-pushgateway:9091"
export PROMETHEUS_ALERTMANAGER_TARGET="hetu-alertmanager:9093"

./scripts/generate-deploy-configs.sh
```

### 4. CI/CD 集成

GitHub Actions workflow 会自动：
1. 从 GitHub Secrets 读取环境变量（如果配置）
2. 使用环境变量生成配置文件
3. 部署到服务器

## 多环境部署

通过配置不同的 GitHub Secrets，可以支持多个环境：

- **生产环境**: 配置 `ALERTMANAGER_WEBHOOK_URL` 等 secrets
- **测试环境**: 配置 `ALERTMANAGER_WEBHOOK_URL_STAGING` 等 secrets
- **开发环境**: 使用默认值或配置 `ALERTMANAGER_WEBHOOK_URL_DEV` 等 secrets

详细说明请参考 `docs/multi-environment-deployment.md`。

## 配置文件差异

### Alertmanager

**生产环境**:
```yaml
url: http://hetu-api:8000/api/scada/alert/notify
```

**开发环境**:
```yaml
url: http://host.docker.internal:18000/api/scada/alert/notify
```

### Prometheus

**生产环境**:
```yaml
url: 'http://hetu-api:8000/api/scada/collector/sd'
```

**开发环境**:
```yaml
url: 'http://host.docker.internal:18000/api/scada/collector/sd'
```

## 相关文档

- `docs/multi-environment-deployment.md`: 多环境部署详细说明
- `docs/cicd-setup.md`: CI/CD 配置说明
- `scripts/generate-deploy-configs.sh`: 配置文件生成脚本
