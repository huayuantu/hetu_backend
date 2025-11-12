#!/bin/bash
# 批量设置 GitHub Secrets
# 使用方法：
#   1. 生成配置文件模板: ./scripts/setup-github-secrets.sh --create-config
#   2. 编辑配置文件: vim github-secrets.conf
#   3. 从配置文件设置: ./scripts/setup-github-secrets.sh --config github-secrets.conf
#   4. 或交互式运行: ./scripts/setup-github-secrets.sh --interactive
#   5. 或设置环境变量后运行: ./scripts/setup-github-secrets.sh

set -e

INTERACTIVE=false
CONFIG_FILE=""
CREATE_CONFIG=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --interactive|-i)
            INTERACTIVE=true
            shift
            ;;
        --config|-c)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --create-config)
            CREATE_CONFIG=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            echo "使用方法:"
            echo "  --create-config    生成配置文件模板"
            echo "  --config FILE      从配置文件读取并设置"
            echo "  --interactive      交互式设置"
            exit 1
            ;;
    esac
done

# 生成配置文件模板
create_config_template() {
    local config_file="${1:-github-secrets.conf}"
    
    if [ -f "$config_file" ]; then
        read -p "配置文件 $config_file 已存在，是否覆盖? (y/n): " overwrite
        if [ "$overwrite" != "y" ] && [ "$overwrite" != "Y" ]; then
            echo "已取消"
            exit 0
        fi
    fi
    
    cat > "$config_file" << 'EOF'
# GitHub Secrets 配置文件
# 填写所有必需的值，然后运行: ./scripts/setup-github-secrets.sh --config github-secrets.conf
# 以 # 开头的行会被忽略

# ==========================================
# 容器镜像服务认证（必需）
# ==========================================
REGISTRY_USERNAME=your-registry-username
REGISTRY_PASSWORD=your-registry-password

# ==========================================
# 部署服务器配置（必需）
# ==========================================
DEPLOY_HOST=your-server-ip-or-domain
DEPLOY_USER=deploy
DEPLOY_PORT=22
DEPLOY_PATH=/opt/hetu-backend
DEPLOY_SSH_KEY_PATH=~/.ssh/id_ed25519

# ==========================================
# 应用环境变量（必需）
# ==========================================
SECRET_KEY=your-django-secret-key-here-change-in-production
DATABASE_URL=postgres://username:password@host:port/dbname

# ==========================================
# 应用环境变量（可选，有默认值）
# ==========================================
DEBUG=False
ALLOWED_HOSTS=your-domain.com,localhost
UPLOAD_ROOT=/etc/api/uploads
CACHE_URL=redis://hetu-redis:6379/0
PROMETHEUS_URL=http://hetu-tsdb:9090
PUSHGATEWAY_URL=http://hetu-pushgateway:9091
PROMETHEUS_RULES_DIR=/etc/prometheus/include
SUPERVISOR_XMLRPC_URL=http://hetu-collector:9001/RPC2
SUPERVISOR_COLLECTOR_COMMAND=python -m apps.scada.script.collector
SUPERVISOR_COLLECTOR_ADVERTISE=hetu-collector
SUPERVISOR_COLLECTOR_DIR=/etc/supervisor/include

# ==========================================
# 服务配置环境变量（可选）
# ==========================================
ALERTMANAGER_WEBHOOK_URL=http://hetu-api:8000/api/scada/alert/notify
PROMETHEUS_SD_URL=http://hetu-api:8000/api/scada/collector/sd
PROMETHEUS_PUSHGATEWAY_TARGET=hetu-pushgateway:9091
PROMETHEUS_ALERTMANAGER_TARGET=hetu-alertmanager:9093

# ==========================================
# 第三方服务配置（可选）
# ==========================================
# 萤石云配置
YS_APPKEY=
YS_APPSECRET=

# IVM 华为云配置
IVM_BASE_URL=https://api-ivm.myhuaweicloud.com
IVM_USER_ID=
IVM_ACCESS_KEY=
IVM_SECRET_KEY=

# 阿里云 OSS 配置
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
EOF
    
    echo "✓ 配置文件模板已创建: $config_file"
    echo ""
    echo "请编辑此文件并填写实际值，然后运行:"
    echo "  ./scripts/setup-github-secrets.sh --config $config_file"
    exit 0
}

# 从配置文件读取并设置
load_config_file() {
    local config_file="$1"
    
    if [ ! -f "$config_file" ]; then
        echo "错误: 配置文件不存在: $config_file"
        exit 1
    fi
    
    echo "从配置文件读取: $config_file"
    echo ""
    
    # 读取配置文件，忽略注释和空行
    while IFS= read -r line || [ -n "$line" ]; do
        # 跳过注释和空行
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$line" ]] && continue
        
        # 去除前后空格
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        # 检查是否包含等号
        if [[ "$line" =~ = ]]; then
            # 分割 key 和 value
            key="${line%%=*}"
            value="${line#*=}"
            
            # 去除 key 和 value 的前后空格
            key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            
            # 展开 ~ 到 $HOME（如果是路径）
            if [[ "$value" =~ ^~ ]]; then
                value="${value/#\~/$HOME}"
            fi
            
            # 设置环境变量
            if [ -n "$key" ]; then
                # 使用 eval 安全地设置环境变量
                eval "export ${key}=\"${value}\""
            fi
        fi
    done < "$config_file"
    
    echo "✓ 配置文件已加载"
    echo ""
}

# 如果请求创建配置文件模板
if [ "$CREATE_CONFIG" = true ]; then
    create_config_template
fi

# 如果指定了配置文件，先加载
if [ -n "$CONFIG_FILE" ]; then
    load_config_file "$CONFIG_FILE"
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

# 显示配置示例
show_example() {
    local name=$1
    local example=$2
    
    case "$name" in
        "SECRET_KEY")
            echo "   示例: django-insecure-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            echo "   提示: 可以使用命令生成: openssl rand -hex 32"
            ;;
        "DATABASE_URL")
            echo "   示例: postgres://user:pass@localhost:5432/hetu_db"
            ;;
        "DEPLOY_HOST")
            echo "   示例: 192.168.1.100 或 deploy.example.com"
            ;;
        "DEPLOY_SSH_KEY_PATH")
            echo "   示例: ~/.ssh/id_ed25519 或 ~/.ssh/id_rsa"
            ;;
        *)
            if [ -n "$example" ]; then
                echo "   示例: $example"
            fi
            ;;
    esac
}

# 设置 Secret 的函数
set_secret() {
    local name=$1
    local description=$2
    local value=$3
    local is_required=${4:-false}
    local example=${5:-""}
    
    if [ -z "$value" ]; then
        if [ "$INTERACTIVE" = true ]; then
            if [ "$is_required" = true ]; then
                show_example "$name" "$example"
                read -sp "输入 $name ($description): " value
                echo ""
            else
                if [ -n "$example" ]; then
                    show_example "$name" "$example"
                fi
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
    
    # 展开 ~ 到 $HOME
    file_path="${file_path/#\~/$HOME}"
    
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
set_secret "REGISTRY_USERNAME" "镜像仓库用户名" "$REGISTRY_USERNAME" true "your-username"
set_secret "REGISTRY_PASSWORD" "镜像仓库密码" "$REGISTRY_PASSWORD" true "your-password"

# 2. 部署服务器配置
echo ""
echo "--- 部署服务器配置 ---"
set_secret "DEPLOY_HOST" "部署服务器地址" "$DEPLOY_HOST" true "192.168.1.100"
set_secret "DEPLOY_USER" "SSH 用户名" "$DEPLOY_USER" true "deploy"
set_secret "DEPLOY_PORT" "SSH 端口" "${DEPLOY_PORT:-22}" false "22"
set_secret "DEPLOY_PATH" "部署路径" "${DEPLOY_PATH:-/opt/hetu-backend}" false "/opt/hetu-backend"

# SSH 密钥
if [ -n "$DEPLOY_SSH_KEY_PATH" ]; then
    set_secret_from_file "DEPLOY_SSH_KEY" "$DEPLOY_SSH_KEY_PATH"
elif [ -f "$HOME/.ssh/id_rsa" ] || [ -f "$HOME/.ssh/id_ed25519" ]; then
    if [ "$INTERACTIVE" = true ]; then
        # 检测常见的 SSH 密钥文件
        default_key=""
        if [ -f "$HOME/.ssh/id_ed25519" ]; then
            default_key="$HOME/.ssh/id_ed25519"
        elif [ -f "$HOME/.ssh/id_rsa" ]; then
            default_key="$HOME/.ssh/id_rsa"
        fi
        
        if [ -n "$default_key" ]; then
            read -p "使用默认 SSH 密钥 ($default_key)? (y/n): " use_default
            if [ "$use_default" = "y" ] || [ "$use_default" = "Y" ]; then
                set_secret_from_file "DEPLOY_SSH_KEY" "$default_key"
            else
                read -p "输入 SSH 密钥文件路径 (支持 ~ 路径): " ssh_key_path
                if [ -n "$ssh_key_path" ]; then
                    set_secret_from_file "DEPLOY_SSH_KEY" "$ssh_key_path"
                fi
            fi
        fi
    else
        echo "⚠ DEPLOY_SSH_KEY 未设置，请手动设置或设置 DEPLOY_SSH_KEY_PATH 环境变量"
    fi
else
    if [ "$INTERACTIVE" = true ]; then
        read -p "输入 SSH 密钥文件路径 (支持 ~ 路径): " ssh_key_path
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
set_secret "SECRET_KEY" "Django SECRET_KEY" "$SECRET_KEY" true ""
set_secret "DATABASE_URL" "数据库连接 URL" "$DATABASE_URL" true "postgres://user:pass@host:5432/dbname"

# 4. 应用环境变量（可选）
echo ""
echo "--- 应用环境变量（可选） ---"
set_secret "DEBUG" "调试模式" "${DEBUG:-False}" false
set_secret "ALLOWED_HOSTS" "允许的主机" "${ALLOWED_HOSTS:-your-domain.com,localhost}" false
set_secret "UPLOAD_ROOT" "上传目录" "${UPLOAD_ROOT:-/etc/api/uploads}" false
set_secret "CACHE_URL" "缓存 URL" "${CACHE_URL:-redis://hetu-redis:6379/0}" false "redis://host:6379/0"
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
set_secret "IVM_BASE_URL" "IVM 基础 URL" "${IVM_BASE_URL:-https://api-ivm.myhuaweicloud.com}" false "https://api-ivm.myhuaweicloud.com"
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

