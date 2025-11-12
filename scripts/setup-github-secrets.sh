#!/bin/bash
# 批量设置 GitHub Secrets
# 使用方法：
#   1. 设置环境变量后运行: ./scripts/setup-github-secrets.sh
#   2. 或交互式运行: ./scripts/setup-github-secrets.sh --interactive

set -e

INTERACTIVE=false

# 解析参数
if [ "$1" == "--interactive" ] || [ "$1" == "-i" ]; then
    INTERACTIVE=true
fi

echo "=========================================="
echo "GitHub Secrets 设置工具"
echo "=========================================="

# 检查 GitHub CLI 是否安装
if ! command -v gh &> /dev/null; then
    echo "错误: 未安装 GitHub CLI (gh)"
    echo ""
    echo "安装方法:"
    echo "  macOS:   brew install gh"
    echo "  Linux:   参考 https://cli.github.com/manual/installation"
    echo "  Windows: winget install GitHub.cli"
    exit 1
fi

# 检查是否已登录
if ! gh auth status &>/dev/null; then
    echo "请先登录 GitHub:"
    echo "  gh auth login"
    exit 1
fi

echo "✓ GitHub CLI 已安装并已登录"
echo ""

# 设置 Secret 的函数
set_secret() {
    local name=$1
    local description=$2
    local value=$3
    local is_required=${4:-false}
    
    if [ -z "$value" ]; then
        if [ "$INTERACTIVE" = true ]; then
            if [ "$is_required" = true ]; then
                read -sp "输入 $name ($description): " value
                echo ""
            else
                read -p "输入 $name ($description，可选，按 Enter 跳过): " value
            fi
        else
            if [ "$is_required" = true ]; then
                echo "⚠ 警告: $name 未设置（必需）"
                return 1
            else
                echo "⊘ $name 跳过（未设置）"
                return 0
            fi
        fi
    fi
    
    if [ -n "$value" ]; then
        echo "$value" | gh secret set "$name"
        echo "✓ $name 已设置"
        return 0
    else
        echo "⊘ $name 跳过"
        return 0
    fi
}

# 从文件读取 Secret
set_secret_from_file() {
    local name=$1
    local file_path=$2
    
    if [ -f "$file_path" ]; then
        gh secret set "$name" < "$file_path"
        echo "✓ $name 已设置（从文件: $file_path）"
        return 0
    else
        echo "⚠ 警告: 文件不存在: $file_path"
        return 1
    fi
}

echo "开始设置 Secrets..."
echo ""

# 1. 容器镜像服务认证
echo "--- 容器镜像服务认证 ---"
set_secret "REGISTRY_USERNAME" "镜像仓库用户名" "$REGISTRY_USERNAME" true
set_secret "REGISTRY_PASSWORD" "镜像仓库密码" "$REGISTRY_PASSWORD" true

# 2. 部署服务器配置
echo ""
echo "--- 部署服务器配置 ---"
set_secret "DEPLOY_HOST" "部署服务器地址" "$DEPLOY_HOST" true
set_secret "DEPLOY_USER" "SSH 用户名" "$DEPLOY_USER" true
set_secret "DEPLOY_PORT" "SSH 端口" "${DEPLOY_PORT:-22}" false
set_secret "DEPLOY_PATH" "部署路径" "${DEPLOY_PATH:-/opt/hetu-backend}" false

# SSH 密钥
if [ -n "$DEPLOY_SSH_KEY_PATH" ]; then
    set_secret_from_file "DEPLOY_SSH_KEY" "$DEPLOY_SSH_KEY_PATH"
elif [ -f "$HOME/.ssh/id_rsa" ]; then
    if [ "$INTERACTIVE" = true ]; then
        read -p "使用默认 SSH 密钥 ($HOME/.ssh/id_rsa)? (y/n): " use_default
        if [ "$use_default" = "y" ] || [ "$use_default" = "Y" ]; then
            set_secret_from_file "DEPLOY_SSH_KEY" "$HOME/.ssh/id_rsa"
        else
            read -p "输入 SSH 密钥文件路径: " ssh_key_path
            if [ -n "$ssh_key_path" ]; then
                set_secret_from_file "DEPLOY_SSH_KEY" "$ssh_key_path"
            fi
        fi
    else
        echo "⚠ DEPLOY_SSH_KEY 未设置，请手动设置或设置 DEPLOY_SSH_KEY_PATH 环境变量"
    fi
else
    if [ "$INTERACTIVE" = true ]; then
        read -p "输入 SSH 密钥文件路径: " ssh_key_path
        if [ -n "$ssh_key_path" ]; then
            set_secret_from_file "DEPLOY_SSH_KEY" "$ssh_key_path"
        fi
    else
        echo "⚠ DEPLOY_SSH_KEY 未设置，请手动设置"
    fi
fi

# 3. 应用环境变量（必需）
echo ""
echo "--- 应用环境变量（必需） ---"
set_secret "SECRET_KEY" "Django SECRET_KEY" "$SECRET_KEY" true
set_secret "DATABASE_URL" "数据库连接 URL" "$DATABASE_URL" true

# 4. 应用环境变量（可选）
echo ""
echo "--- 应用环境变量（可选） ---"
set_secret "DEBUG" "调试模式" "${DEBUG:-False}" false
set_secret "ALLOWED_HOSTS" "允许的主机" "${ALLOWED_HOSTS:-your-domain.com,localhost}" false
set_secret "UPLOAD_ROOT" "上传目录" "${UPLOAD_ROOT:-/etc/api/uploads}" false
set_secret "PROMETHEUS_URL" "Prometheus 地址" "${PROMETHEUS_URL:-http://hetu-tsdb:9090}" false
set_secret "PUSHGATEWAY_URL" "Pushgateway 地址" "${PUSHGATEWAY_URL:-http://hetu-pushgateway:9091}" false
set_secret "PROMETHEUS_RULES_DIR" "Prometheus 规则目录" "${PROMETHEUS_RULES_DIR:-/etc/prometheus/include}" false
set_secret "SUPERVISOR_XMLRPC_URL" "Supervisor XML-RPC 地址" "${SUPERVISOR_XMLRPC_URL:-http://hetu-collector:9001/RPC2}" false
set_secret "SUPERVISOR_COLLECTOR_COMMAND" "Collector 命令" "${SUPERVISOR_COLLECTOR_COMMAND:-python -m apps.scada.script.collector}" false
set_secret "SUPERVISOR_COLLECTOR_ADVERTISE" "Collector 暴露地址" "${SUPERVISOR_COLLECTOR_ADVERTISE:-hetu-collector}" false
set_secret "SUPERVISOR_COLLECTOR_DIR" "Collector 配置目录" "${SUPERVISOR_COLLECTOR_DIR:-/etc/supervisor/include}" false

# 5. 服务配置环境变量（可选）
echo ""
echo "--- 服务配置环境变量（可选） ---"
set_secret "ALERTMANAGER_WEBHOOK_URL" "Alertmanager webhook URL" "$ALERTMANAGER_WEBHOOK_URL" false
set_secret "PROMETHEUS_SD_URL" "Prometheus 服务发现 URL" "$PROMETHEUS_SD_URL" false
set_secret "PROMETHEUS_PUSHGATEWAY_TARGET" "Pushgateway 目标" "$PROMETHEUS_PUSHGATEWAY_TARGET" false
set_secret "PROMETHEUS_ALERTMANAGER_TARGET" "Alertmanager 目标" "$PROMETHEUS_ALERTMANAGER_TARGET" false

# 6. 第三方服务配置（可选）
echo ""
echo "--- 第三方服务配置（可选） ---"
set_secret "YS_APPKEY" "萤石云 AppKey" "$YS_APPKEY" false
set_secret "YS_APPSECRET" "萤石云 AppSecret" "$YS_APPSECRET" false
set_secret "IVM_USER_ID" "IVM 用户 ID" "$IVM_USER_ID" false
set_secret "IVM_ACCESS_KEY" "IVM Access Key" "$IVM_ACCESS_KEY" false
set_secret "IVM_SECRET_KEY" "IVM Secret Key" "$IVM_SECRET_KEY" false
set_secret "OSS_ACCESS_KEY_ID" "OSS Access Key ID" "$OSS_ACCESS_KEY_ID" false
set_secret "OSS_ACCESS_KEY_SECRET" "OSS Access Key Secret" "$OSS_ACCESS_KEY_SECRET" false

echo ""
echo "=========================================="
echo "Secrets 设置完成！"
echo "=========================================="
echo ""
echo "查看已设置的 secrets:"
gh secret list

