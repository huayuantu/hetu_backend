# CI/CD 快速参考

## 快速开始

### 1. 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 secrets：

```
REGISTRY_USERNAME          # 镜像仓库用户名
REGISTRY_PASSWORD          # 镜像仓库密码
DEPLOY_HOST                # 部署服务器地址
DEPLOY_USER                # SSH 用户名
DEPLOY_SSH_KEY             # SSH 私钥（完整内容）
DEPLOY_PORT                # SSH 端口（可选，默认 22）
DEPLOY_PATH                # 部署路径（可选，默认 /opt/hetu-backend）
```

### 2. 配置 GitHub Secrets（用于生成 .env 文件）

在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中添加：

**必需**:
- `SECRET_KEY`: Django 密钥
- `DATABASE_URL`: 数据库连接 URL

**可选**（有默认值）:
- `DEBUG`, `ALLOWED_HOSTS`, `UPLOAD_ROOT` 等
- 参考 `docs/cicd-setup.md` 查看完整列表

### 3. 部署服务器准备

```bash
# 创建部署目录（仅此一步，所有文件由 CI/CD 自动同步）
mkdir -p /opt/hetu-backend
chmod 755 /opt/hetu-backend

# .env 文件会由 GitHub Actions 自动生成并同步
```

### 4. 创建版本并部署

```bash
# 创建版本 tag
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions 会自动构建和部署
```

## 环境变量配置

### 部署机器上的 .env 文件

部署服务器上的 `.env` 文件应包含所有必要的环境变量，参考 `docs/cicd-setup.md` 中的完整列表。

**重要**: `.env` 文件包含敏感信息，不要提交到 Git。

### Docker Compose 环境变量

在部署时，以下环境变量会被自动设置：

- `REGISTRY`: 镜像仓库地址（从 GitHub Actions env 传递）
- `IMAGE_NAME`: 镜像名称（从 GitHub Actions env 传递）
- `HETU_VERSION`: 版本号（从 Git tag 提取）

## 版本管理

### 版本号格式

使用语义化版本号（Semantic Versioning）：

- `v1.0.0`: 主版本号（重大变更）
- `v1.1.0`: 次版本号（新功能）
- `v1.1.1`: 修订号（bug 修复）

### 镜像标签

- 版本镜像: `hetu_xinhong/hetu-backend:1.0.0-base` / `1.0.0-collector`
- 最新镜像: `hetu_xinhong/hetu-backend:latest-base` / `latest-collector`

### 回滚

```bash
cd /opt/hetu-backend
export REGISTRY="crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com"
export IMAGE_NAME="hetu_xinhong/hetu-backend"
export HETU_VERSION="0.9.0"  # 要回滚的版本号
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --no-deps api collector
```

## 工作流程

```
推送 Tag (v1.0.0)
    ↓
GitHub Actions 触发
    ↓
构建 Docker 镜像 (base + collector)
    ↓
推送到镜像仓库
    ↓
SSH 连接到部署服务器
    ↓
拉取镜像
    ↓
更新 docker-compose 服务
    ↓
部署完成
```

## 常见问题

### 1. 如何查看部署日志？

```bash
# GitHub Actions
在 GitHub 仓库的 Actions 标签页查看

# 部署服务器
cd /opt/hetu-backend
docker-compose -f docker-compose.prod.yml logs -f
```

### 2. 如何手动部署？

```bash
cd /opt/hetu-backend
export HETU_VERSION=1.0.0
export REGISTRY="crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com"
export IMAGE_NAME="hetu_xinhong/hetu-backend"
./scripts/deploy.sh
```

### 3. 如何检查服务状态？

```bash
cd /opt/hetu-backend
docker-compose -f docker-compose.prod.yml ps
curl http://localhost:8000/-/healthy
```

## 相关文件

- `.github/workflows/deploy.yml`: CI/CD 工作流配置
- `docker-compose.prod.yml`: Docker Compose 配置
- `scripts/deploy.sh`: 手动部署脚本
- `docs/cicd-setup.md`: 详细配置文档

