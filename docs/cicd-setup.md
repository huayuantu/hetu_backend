# CI/CD 配置说明

## 概述

本项目使用 GitHub Actions 实现自动化构建和部署。当推送特定格式的 Git tag 时，会自动构建 Docker 镜像并部署到服务器。

## 工作流程

1. **触发条件**: 推送以 `v` 开头的 tag（如 `v1.0.0`）
2. **构建阶段**: 构建两个 Docker 镜像（base 和 collector）
3. **推送阶段**: 将镜像推送到阿里云容器镜像服务
4. **部署阶段**: SSH 连接到部署服务器，拉取镜像并更新服务

## 配置步骤

### 1. GitHub Secrets 配置

在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中添加以下 secrets：

#### 容器镜像服务认证
- `REGISTRY_USERNAME`: 阿里云容器镜像服务的用户名
- `REGISTRY_PASSWORD`: 阿里云容器镜像服务的密码

#### 部署服务器配置
- `DEPLOY_HOST`: 部署服务器的 IP 地址或域名
- `DEPLOY_USER`: SSH 登录用户名
- `DEPLOY_SSH_KEY`: SSH 私钥（完整内容，包括 `-----BEGIN ... KEY-----` 和 `-----END ... KEY-----`）
- `DEPLOY_PORT`: SSH 端口（可选，默认 22）
- `DEPLOY_PATH`: 部署路径（可选，默认 `/opt/hetu-backend`）

#### 服务配置环境变量（可选，支持多环境部署）
- `ALERTMANAGER_WEBHOOK_URL`: Alertmanager webhook 回调地址（默认: `http://hetu-api:8000/api/scada/alert/notify`）
- `PROMETHEUS_SD_URL`: Prometheus 服务发现 URL（默认: `http://hetu-api:8000/api/scada/collector/sd`）
- `PROMETHEUS_PUSHGATEWAY_TARGET`: Pushgateway 目标地址（默认: `hetu-pushgateway:9091`）
- `PROMETHEUS_ALERTMANAGER_TARGET`: Alertmanager 目标地址（默认: `hetu-alertmanager:9093`）

#### 应用环境变量（必需，用于生成 .env 文件）
以下环境变量用于自动生成部署服务器的 `.env` 文件：

**必需的环境变量**:
- `SECRET_KEY`: Django 密钥（必须配置）
- `DATABASE_URL`: 数据库连接 URL（必须配置）

**可选的环境变量**（有默认值）:
- `DEBUG`: Django 调试模式（默认: `False`）
- `ALLOWED_HOSTS`: 允许的主机列表（默认: `your-domain.com,localhost`）
- `UPLOAD_ROOT`: 上传目录（默认: `/etc/api/uploads`）
- `PROMETHEUS_URL`: Prometheus 地址（默认: `http://hetu-tsdb:9090`）
- `PUSHGATEWAY_URL`: Pushgateway 地址（默认: `http://hetu-pushgateway:9091`）
- `PROMETHEUS_RULES_DIR`: Prometheus 规则目录（默认: `/etc/prometheus/include`）
- `SUPERVISOR_XMLRPC_URL`: Supervisor XML-RPC 地址（默认: `http://hetu-collector:9001/RPC2`）
- `SUPERVISOR_COLLECTOR_COMMAND`: Collector 命令（默认: `python -m apps.scada.script.collector`）
- `SUPERVISOR_COLLECTOR_ADVERTISE`: Collector 暴露地址（默认: `hetu-collector`）
- `SUPERVISOR_COLLECTOR_DIR`: Collector 配置目录（默认: `/etc/supervisor/include`）

**可选的服务配置**（如果使用）:
- `YS_APPKEY`: 萤石云 AppKey
- `YS_APPSECRET`: 萤石云 AppSecret
- `IVM_BASE_URL`: IVM 基础 URL（默认: `https://api-ivm.myhuaweicloud.com`）
- `IVM_USER_ID`: IVM 用户 ID
- `IVM_ACCESS_KEY`: IVM Access Key
- `IVM_SECRET_KEY`: IVM Secret Key
- `OSS_ENDPOINT`: OSS 端点（默认: `oss-cn-shanghai.aliyuncs.com`）
- `OSS_BUCKET_NAME`: OSS 存储桶名称（默认: `hetu-scada`）
- `OSS_ACCESS_KEY_ID`: OSS Access Key ID
- `OSS_ACCESS_KEY_SECRET`: OSS Access Key Secret

**注意**: 
- 如果不配置服务配置环境变量，将使用 workflow 中的默认值
- `.env` 文件会由 GitHub Actions 自动生成并同步到部署服务器
- 配置这些变量可以支持部署到多个不同的环境。详细说明请参考 `docs/multi-environment-deployment.md`。

### 2. 部署服务器准备

#### 2.1 创建部署目录

部署服务器只需要准备目录，所有文件会由 GitHub Actions 自动同步。

```bash
# 创建部署目录
sudo mkdir -p /opt/hetu-backend
sudo chown $USER:$USER /opt/hetu-backend

# 确保目录权限正确
chmod 755 /opt/hetu-backend
```

**注意**: 
- 不需要克隆仓库或手动复制文件
- 不需要手动创建 `.env` 文件
- GitHub Actions 会自动：
  1. 从 GitHub Secrets 读取环境变量
  2. 生成 `.env` 文件
  3. 同步以下文件到部署服务器：
     - `.env`（自动生成）
     - `docker-compose.prod.yml`
     - `gunicorn_config.py`
     - `deploy/` 目录（包含所有配置文件模板）
     - `scripts/` 目录（包含部署脚本）

#### 2.2 配置 GitHub Secrets（用于生成 .env 文件）

**重要**: `.env` 文件现在由 GitHub Actions 自动生成，需要在 GitHub Secrets 中配置所有必需的环境变量。

在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中添加以下 secrets：

**必需的环境变量**（必须配置）:
- `SECRET_KEY`: Django 密钥
- `DATABASE_URL`: 数据库连接 URL（格式: `postgres://user:password@host:port/dbname`）

**可选的环境变量**（有默认值，可根据需要配置）:
- `DEBUG`: Django 调试模式
- `ALLOWED_HOSTS`: 允许的主机列表
- `UPLOAD_ROOT`: 上传目录
- `PROMETHEUS_URL`: Prometheus 地址
- `PUSHGATEWAY_URL`: Pushgateway 地址
- `PROMETHEUS_RULES_DIR`: Prometheus 规则目录
- `SUPERVISOR_XMLRPC_URL`: Supervisor XML-RPC 地址
- `SUPERVISOR_COLLECTOR_COMMAND`: Collector 命令
- `SUPERVISOR_COLLECTOR_ADVERTISE`: Collector 暴露地址
- `SUPERVISOR_COLLECTOR_DIR`: Collector 配置目录

**服务配置**（如果使用相关服务）:
- `YS_APPKEY`, `YS_APPSECRET`: 萤石云配置
- `IVM_USER_ID`, `IVM_ACCESS_KEY`, `IVM_SECRET_KEY`: IVM 华为云配置
- `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`: 阿里云 OSS 配置

`.env` 文件示例（仅供参考，实际文件由 CI/CD 自动生成）：

```bash
# Django 配置
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=your-domain.com,localhost

# 上传目录
UPLOAD_ROOT=/etc/api/uploads

# 数据库配置 (格式: postgres://user:password@host:port/dbname 或 postgresql://...)
DATABASE_URL=postgres://hetu:hetu@hetu-db:5432/hetu

# Prometheus 配置
PROMETHEUS_URL=http://hetu-tsdb:9090
PUSHGATEWAY_URL=http://hetu-pushgateway:9091
PROMETHEUS_RULES_DIR=/etc/prometheus/include

# Supervisor 配置
SUPERVISOR_XMLRPC_URL=http://hetu-collector:9001/RPC2
SUPERVISOR_COLLECTOR_COMMAND=python -m apps.scada.script.collector
SUPERVISOR_COLLECTOR_ADVERTISE=hetu-collector
SUPERVISOR_COLLECTOR_DIR=/etc/supervisor/include

# 萤石云配置（可选，如不需要可以留空）
YS_APPKEY=your-appkey
YS_APPSECRET=your-appsecret

# IVM 华为云配置（可选，如不需要可以留空）
IVM_BASE_URL=https://api-ivm.myhuaweicloud.com
IVM_USER_ID=your-user-id
IVM_ACCESS_KEY=your-access-key
IVM_SECRET_KEY=your-secret-key

# 阿里云 OSS 配置（可选，如不需要可以留空）
OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
OSS_BUCKET_NAME=hetu-scada
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
```

**注意**: 
- `.env` 文件包含敏感信息，已在 `.gitignore` 中，不会被提交到 Git
- `.env` 文件由 GitHub Actions 自动生成并同步到部署服务器
- 所有环境变量通过 GitHub Secrets 配置，支持多环境部署

**文件说明**:
- `env.template`: 用于 CI/CD 自动生成 `.env` 文件（包含 `${VAR}` 占位符，由 GitHub Actions 使用）
- `env.example`: 用于文档参考和本地开发（包含示例值，便于开发者理解需要配置哪些变量）

详细说明请参考 `docs/env-files-explanation.md`。

#### 2.3 配置文件生成（自动）

部署服务器上的配置文件（`alertmanager.yml`、`prometheus.yml`、`supervisord.conf`）会在 CI/CD 部署时自动从模板文件生成，使用环境变量替换占位符。

**配置文件说明**:
- `*.yml.template`: 模板文件，包含环境变量占位符（如 `${ALERTMANAGER_WEBHOOK_URL}`）
- `*.yml`: 生成的配置文件，环境变量已被替换

**多环境支持**: 通过配置不同的 GitHub Secrets，可以支持部署到多个环境。详细说明请参考 `docs/multi-environment-deployment.md`。

#### 2.4 配置 SSH 密钥认证

在部署服务器上配置 SSH 密钥，允许 GitHub Actions 通过 SSH 连接：

```bash
# 在部署服务器上创建 .ssh 目录（如果不存在）
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 将 GitHub Actions 使用的公钥添加到 authorized_keys
# （需要先在 GitHub Secrets 中配置对应的私钥）
```

或者，可以创建一个专用的部署用户：

```bash
sudo useradd -m -s /bin/bash deploy
sudo mkdir -p /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
# 将公钥添加到 /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
```

#### 2.5 安装 Docker 和 Docker Compose

确保部署服务器已安装 Docker 和 Docker Compose：

```bash
# 检查 Docker
docker --version
docker-compose --version
```

### 3. 版本管理

#### 3.1 创建版本 Tag

使用语义化版本号（Semantic Versioning）创建 tag：

```bash
# 主版本号.次版本号.修订号
git tag v1.0.0
git push origin v1.0.0
```

版本号格式：
- `v1.0.0`: 主版本号（重大变更）
- `v1.1.0`: 次版本号（新功能）
- `v1.1.1`: 修订号（bug 修复）

#### 3.2 镜像标签规则

- 版本镜像: `hetu_xinhong/hetu-backend:1.0.0-base` 和 `hetu_xinhong/hetu-backend:1.0.0-collector`
- 最新镜像: `hetu_xinhong/hetu-backend:latest-base` 和 `hetu_xinhong/hetu-backend:latest-collector`

#### 3.3 回滚到旧版本

如果需要回滚到之前的版本：

```bash
cd /opt/hetu-backend
export HETU_VERSION=1.0.0  # 替换为要回滚的版本号
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --no-deps api collector
```

## 部署流程

### 自动部署（推荐）

1. 在本地开发并测试
2. 提交代码并推送到 GitHub
3. 创建并推送版本 tag：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. GitHub Actions 会自动：
   - 构建 Docker 镜像
   - 推送到镜像仓库
   - 连接到部署服务器
   - 拉取镜像并更新服务

### 手动部署

如果需要在部署服务器上手动部署：

```bash
cd /opt/hetu-backend
export HETU_VERSION=1.0.0
./scripts/deploy.sh
```

或者直接使用 docker-compose：

```bash
cd /opt/hetu-backend
export HETU_VERSION=1.0.0
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## 监控和日志

### 查看服务状态

```bash
cd /opt/hetu-backend
docker-compose -f docker-compose.prod.yml ps
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.prod.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f collector
```

### 健康检查

API 服务提供健康检查端点：

```bash
curl http://localhost:8000/-/healthy
```

## 故障排查

### 1. GitHub Actions 构建失败

- 检查 Dockerfile 是否正确
- 检查依赖是否完整
- 查看 GitHub Actions 日志

### 2. SSH 连接失败

- 检查 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_SSH_KEY` 是否正确
- 检查部署服务器的防火墙设置
- 测试 SSH 连接：`ssh -i <key-file> <user>@<host>`

### 3. 镜像拉取失败

- 检查容器镜像服务认证信息是否正确
- 检查镜像是否成功推送到仓库
- 在部署服务器上手动测试：`docker pull <image-url>`

### 4. 服务启动失败

- 检查 `.env` 文件配置是否正确
- 查看服务日志：`docker-compose logs <service-name>`
- 检查端口是否被占用
- 检查数据库连接是否正常

## 安全建议

1. **环境变量**: 所有敏感信息存储在 `.env` 文件中，不要提交到 Git
2. **SSH 密钥**: 使用专用的部署密钥，定期轮换
3. **镜像仓库**: 使用私有镜像仓库，限制访问权限
4. **网络**: 部署服务器应该配置防火墙，只开放必要端口
5. **备份**: 定期备份数据库和配置文件

## 相关文件

- `.github/workflows/deploy.yml`: GitHub Actions 工作流配置
- `Dockerfile`: Docker 镜像构建配置
- `docker-compose.prod.yml`: Docker Compose 服务配置
- `scripts/deploy.sh`: 手动部署脚本

