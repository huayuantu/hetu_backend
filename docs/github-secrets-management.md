# GitHub Secrets 和 Environment Variables 管理

## 工具：GitHub CLI (gh)

使用 GitHub CLI (`gh`) 可以通过命令行管理 GitHub Secrets 和 Environment Variables。

### 安装 GitHub CLI

```bash
# macOS
brew install gh

# Linux
# Debian/Ubuntu
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Windows
winget install GitHub.cli
# 或
scoop install gh
```

### 认证

```bash
# 登录 GitHub
gh auth login

# 选择认证方式：
# 1. GitHub.com
# 2. HTTPS
# 3. 浏览器登录（推荐）或 Token
```

## 管理 Repository Secrets

### 添加 Secret

```bash
# 基本语法
gh secret set <SECRET_NAME> --body "<secret-value>"

# 示例：添加 SECRET_KEY
gh secret set SECRET_KEY --body "your-secret-key-value"

# 从文件读取（推荐，避免在命令行中暴露）
gh secret set SECRET_KEY < secret-key.txt

# 从环境变量读取
echo "$SECRET_KEY_VALUE" | gh secret set SECRET_KEY

# 批量设置（使用脚本）
cat <<EOF | gh secret set SECRET_KEY --body "$(cat)"
your-secret-key-value
EOF
```

### 查看 Secrets 列表

```bash
# 列出所有 secrets（只显示名称，不显示值）
gh secret list
```

### 删除 Secret

```bash
gh secret delete SECRET_KEY
```

### 批量设置 Secrets

创建脚本 `scripts/setup-github-secrets.sh`:

```bash
#!/bin/bash
# 批量设置 GitHub Secrets

set -e

# 检查是否已登录
if ! gh auth status &>/dev/null; then
    echo "请先登录 GitHub: gh auth login"
    exit 1
fi

# 从环境变量或文件读取并设置
# 方式1: 从环境变量读取
if [ -n "$SECRET_KEY" ]; then
    echo "$SECRET_KEY" | gh secret set SECRET_KEY
    echo "✓ SECRET_KEY 已设置"
fi

if [ -n "$DATABASE_URL" ]; then
    echo "$DATABASE_URL" | gh secret set DATABASE_URL
    echo "✓ DATABASE_URL 已设置"
fi

# 方式2: 从文件读取
if [ -f ".secrets/SECRET_KEY" ]; then
    gh secret set SECRET_KEY < .secrets/SECRET_KEY
    echo "✓ SECRET_KEY 已设置（从文件）"
fi

# 设置部署相关 secrets
if [ -n "$DEPLOY_HOST" ]; then
    echo "$DEPLOY_HOST" | gh secret set DEPLOY_HOST
    echo "✓ DEPLOY_HOST 已设置"
fi

if [ -n "$DEPLOY_USER" ]; then
    echo "$DEPLOY_USER" | gh secret set DEPLOY_USER
    echo "✓ DEPLOY_USER 已设置"
fi

# SSH 密钥（从文件读取）
if [ -f "$HOME/.ssh/deploy_key" ]; then
    gh secret set DEPLOY_SSH_KEY < "$HOME/.ssh/deploy_key"
    echo "✓ DEPLOY_SSH_KEY 已设置"
fi

echo "所有 secrets 设置完成！"
```

## 管理 Environment Variables

GitHub Actions 支持 Environment Variables，可以用于不同环境的配置。

### 创建 Environment

```bash
# 创建环境（如果不存在）
# 注意：environments 需要在仓库设置中创建，CLI 主要用于设置变量
```

### 设置 Environment Variable

```bash
# 为特定环境设置变量
gh variable set <VARIABLE_NAME> --body "<value>" --env <environment>

# 示例：为 production 环境设置变量
gh variable set ALERTMANAGER_WEBHOOK_URL \
    --body "http://hetu-api:8000/api/scada/alert/notify" \
    --env production
```

### 查看 Environment Variables

```bash
# 列出所有环境变量
gh variable list

# 列出特定环境的变量
gh variable list --env production
```

## 完整示例脚本

创建 `scripts/setup-all-secrets.sh`:

```bash
#!/bin/bash
# 设置所有必需的 GitHub Secrets

set -e

REPO="huayuantu/hetu_backend"  # 替换为你的仓库

echo "=========================================="
echo "设置 GitHub Secrets"
echo "=========================================="

# 检查是否已登录
if ! gh auth status &>/dev/null; then
    echo "请先登录 GitHub: gh auth login"
    exit 1
fi

# 切换到正确的仓库目录（如果需要）
# cd /path/to/repo

# 1. 容器镜像服务认证
read -sp "输入 REGISTRY_USERNAME: " REGISTRY_USERNAME
echo ""
echo "$REGISTRY_USERNAME" | gh secret set REGISTRY_USERNAME
echo "✓ REGISTRY_USERNAME 已设置"

read -sp "输入 REGISTRY_PASSWORD: " REGISTRY_PASSWORD
echo ""
echo "$REGISTRY_PASSWORD" | gh secret set REGISTRY_PASSWORD
echo "✓ REGISTRY_PASSWORD 已设置"

# 2. 部署服务器配置
read -p "输入 DEPLOY_HOST: " DEPLOY_HOST
echo "$DEPLOY_HOST" | gh secret set DEPLOY_HOST
echo "✓ DEPLOY_HOST 已设置"

read -p "输入 DEPLOY_USER: " DEPLOY_USER
echo "$DEPLOY_USER" | gh secret set DEPLOY_USER
echo "✓ DEPLOY_USER 已设置"

read -p "输入 DEPLOY_PORT (默认 22): " DEPLOY_PORT
DEPLOY_PORT=${DEPLOY_PORT:-22}
echo "$DEPLOY_PORT" | gh secret set DEPLOY_PORT
echo "✓ DEPLOY_PORT 已设置"

read -p "输入 DEPLOY_PATH (默认 /opt/hetu-backend): " DEPLOY_PATH
DEPLOY_PATH=${DEPLOY_PATH:-/opt/hetu-backend}
echo "$DEPLOY_PATH" | gh secret set DEPLOY_PATH
echo "✓ DEPLOY_PATH 已设置"

# SSH 密钥
read -p "输入 SSH 密钥文件路径 (默认 ~/.ssh/id_rsa): " SSH_KEY_PATH
SSH_KEY_PATH=${SSH_KEY_PATH:-~/.ssh/id_rsa}
if [ -f "$SSH_KEY_PATH" ]; then
    gh secret set DEPLOY_SSH_KEY < "$SSH_KEY_PATH"
    echo "✓ DEPLOY_SSH_KEY 已设置"
else
    echo "⚠ SSH 密钥文件不存在: $SSH_KEY_PATH"
fi

# 3. 应用环境变量（必需）
read -sp "输入 SECRET_KEY: " SECRET_KEY
echo ""
echo "$SECRET_KEY" | gh secret set SECRET_KEY
echo "✓ SECRET_KEY 已设置"

read -p "输入 DATABASE_URL: " DATABASE_URL
echo "$DATABASE_URL" | gh secret set DATABASE_URL
echo "✓ DATABASE_URL 已设置"

# 4. 可选环境变量
read -p "输入 ALLOWED_HOSTS (默认 your-domain.com,localhost): " ALLOWED_HOSTS
ALLOWED_HOSTS=${ALLOWED_HOSTS:-your-domain.com,localhost}
echo "$ALLOWED_HOSTS" | gh secret set ALLOWED_HOSTS
echo "✓ ALLOWED_HOSTS 已设置"

# 5. 服务配置环境变量（可选）
read -p "输入 ALERTMANAGER_WEBHOOK_URL (可选，按 Enter 跳过): " ALERTMANAGER_WEBHOOK_URL
if [ -n "$ALERTMANAGER_WEBHOOK_URL" ]; then
    echo "$ALERTMANAGER_WEBHOOK_URL" | gh secret set ALERTMANAGER_WEBHOOK_URL
    echo "✓ ALERTMANAGER_WEBHOOK_URL 已设置"
fi

read -p "输入 PROMETHEUS_SD_URL (可选，按 Enter 跳过): " PROMETHEUS_SD_URL
if [ -n "$PROMETHEUS_SD_URL" ]; then
    echo "$PROMETHEUS_SD_URL" | gh secret set PROMETHEUS_SD_URL
    echo "✓ PROMETHEUS_SD_URL 已设置"
fi

echo "=========================================="
echo "所有 Secrets 设置完成！"
echo "=========================================="
echo ""
echo "查看已设置的 secrets:"
gh secret list
```

## 从文件批量导入

创建 `.secrets/` 目录存储敏感信息（已添加到 .gitignore）：

```bash
# 创建 secrets 目录
mkdir -p .secrets

# 创建示例文件（不要提交到 Git）
cat > .secrets/example.txt <<EOF
# 复制此文件为实际文件，填入真实值
# 例如：.secrets/production.txt

REGISTRY_USERNAME=your-username
REGISTRY_PASSWORD=your-password
DEPLOY_HOST=your-server-ip
DEPLOY_USER=deploy
DEPLOY_SSH_KEY_PATH=~/.ssh/deploy_key
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@host:5432/db
EOF
```

创建导入脚本 `scripts/import-secrets-from-file.sh`:

```bash
#!/bin/bash
# 从文件导入 GitHub Secrets

set -e

SECRETS_FILE="${1:-.secrets/production.txt}"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "错误: 文件不存在: $SECRETS_FILE"
    echo "用法: $0 <secrets-file>"
    exit 1
fi

echo "从 $SECRETS_FILE 导入 secrets..."

# 读取文件并设置 secrets
while IFS='=' read -r key value; do
    # 跳过注释和空行
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    
    # 处理特殊键（如 SSH_KEY_PATH）
    if [ "$key" == "DEPLOY_SSH_KEY_PATH" ]; then
        if [ -f "$value" ]; then
            gh secret set DEPLOY_SSH_KEY < "$value"
            echo "✓ DEPLOY_SSH_KEY 已设置（从 $value）"
        fi
        continue
    fi
    
    # 设置 secret
    echo "$value" | gh secret set "$key"
    echo "✓ $key 已设置"
done < "$SECRETS_FILE"

echo "导入完成！"
```

## 安全建议

1. **不要将 secrets 文件提交到 Git**
   ```bash
   # 添加到 .gitignore
   echo ".secrets/" >> .gitignore
   ```

2. **使用文件而不是命令行参数**
   ```bash
   # 好：从文件读取
   gh secret set SECRET_KEY < secret.txt
   
   # 不好：直接在命令行中暴露
   gh secret set SECRET_KEY --body "secret-value"
   ```

3. **使用环境变量**
   ```bash
   # 从环境变量读取
   echo "$SECRET_VALUE" | gh secret set SECRET_KEY
   ```

4. **验证设置**
   ```bash
   # 列出所有 secrets 验证
   gh secret list
   ```

## 常用命令速查

```bash
# 认证
gh auth login                    # 登录
gh auth status                  # 查看认证状态
gh auth logout                  # 登出

# Secrets 管理
gh secret list                  # 列出所有 secrets
gh secret set NAME --body VALUE # 设置 secret
gh secret delete NAME           # 删除 secret

# Variables 管理
gh variable list                 # 列出所有变量
gh variable set NAME --body VALUE # 设置变量
gh variable set NAME --body VALUE --env ENV # 为环境设置变量
gh variable delete NAME          # 删除变量

# 查看仓库信息
gh repo view                    # 查看仓库信息
gh repo set-default             # 设置默认仓库
```

## 参考文档

- [GitHub CLI 官方文档](https://cli.github.com/manual/)
- [GitHub Secrets 文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GitHub Variables 文档](https://docs.github.com/en/actions/learn-github-actions/variables)

