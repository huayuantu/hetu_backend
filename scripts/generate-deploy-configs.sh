#!/bin/bash
# 从模板文件生成部署配置文件
# 使用环境变量替换模板中的占位符

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "生成部署配置文件"
echo "=========================================="

# 检查必需的环境变量
REQUIRED_VARS=(
    "ALERTMANAGER_WEBHOOK_URL"
    "PROMETHEUS_SD_URL"
    "PROMETHEUS_PUSHGATEWAY_TARGET"
    "PROMETHEUS_ALERTMANAGER_TARGET"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "错误: 以下必需的环境变量未设置:"
    printf '  - %s\n' "${MISSING_VARS[@]}"
    echo ""
    echo "请设置这些环境变量后再运行此脚本"
    exit 1
fi

# 显示使用的环境变量值
echo "使用的环境变量:"
echo "  ALERTMANAGER_WEBHOOK_URL=${ALERTMANAGER_WEBHOOK_URL}"
echo "  PROMETHEUS_SD_URL=${PROMETHEUS_SD_URL}"
echo "  PROMETHEUS_PUSHGATEWAY_TARGET=${PROMETHEUS_PUSHGATEWAY_TARGET}"
echo "  PROMETHEUS_ALERTMANAGER_TARGET=${PROMETHEUS_ALERTMANAGER_TARGET}"
echo "=========================================="

# 生成 Alertmanager 配置
if [ -f "deploy/alertmanager/alertmanager.yml.template" ]; then
    echo "生成 alertmanager.yml..."
    envsubst < deploy/alertmanager/alertmanager.yml.template > deploy/alertmanager/alertmanager.yml
    echo "✓ alertmanager.yml 已生成"
else
    echo "⚠ 警告: alertmanager.yml.template 不存在"
fi

# 生成 Prometheus 配置
if [ -f "deploy/prometheus/prometheus.yml.template" ]; then
    echo "生成 prometheus.yml..."
    envsubst < deploy/prometheus/prometheus.yml.template > deploy/prometheus/prometheus.yml
    echo "✓ prometheus.yml 已生成"
else
    echo "⚠ 警告: prometheus.yml.template 不存在"
fi

# Supervisor 配置（目前不需要环境变量，直接复制）
if [ -f "deploy/supervisor/supervisord.default.conf" ]; then
    echo "复制 supervisord.conf..."
    cp deploy/supervisor/supervisord.default.conf deploy/supervisor/supervisord.conf
    echo "✓ supervisord.conf 已复制"
else
    echo "⚠ 警告: supervisord.default.conf 不存在"
fi

echo "=========================================="
echo "配置文件生成完成"
echo "=========================================="

# 验证生成的文件
echo ""
echo "验证生成的文件..."
for config_file in \
    "deploy/alertmanager/alertmanager.yml" \
    "deploy/prometheus/prometheus.yml" \
    "deploy/supervisor/supervisord.conf"
do
    if [ -f "$config_file" ]; then
        echo "✓ $config_file 存在"
    else
        echo "✗ $config_file 不存在"
        exit 1
    fi
done

echo ""
echo "所有配置文件验证通过！"

