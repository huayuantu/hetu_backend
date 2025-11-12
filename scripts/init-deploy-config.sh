#!/bin/bash
# 初始化部署配置文件（已废弃，请使用 generate-deploy-configs.sh）
# 此脚本保留用于向后兼容，实际会调用 generate-deploy-configs.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "初始化部署配置文件（兼容模式）"
echo "=========================================="
echo "注意: 此脚本已废弃，请使用 generate-deploy-configs.sh"
echo "=========================================="

# 设置默认环境变量（如果没有设置）
export ALERTMANAGER_WEBHOOK_URL="${ALERTMANAGER_WEBHOOK_URL:-http://hetu-api:8000/api/scada/alert/notify}"
export PROMETHEUS_SD_URL="${PROMETHEUS_SD_URL:-http://hetu-api:8000/api/scada/collector/sd}"
export PROMETHEUS_PUSHGATEWAY_TARGET="${PROMETHEUS_PUSHGATEWAY_TARGET:-hetu-pushgateway:9091}"
export PROMETHEUS_ALERTMANAGER_TARGET="${PROMETHEUS_ALERTMANAGER_TARGET:-hetu-alertmanager:9093}"

# 如果 generate-deploy-configs.sh 存在，使用它
if [ -f "scripts/generate-deploy-configs.sh" ]; then
    echo "使用 generate-deploy-configs.sh..."
    chmod +x scripts/generate-deploy-configs.sh
    ./scripts/generate-deploy-configs.sh
else
    echo "警告: generate-deploy-configs.sh 不存在，使用旧的复制方式"
    # 回退到旧的复制方式
    cp deploy/alertmanager/alertmanager.default.yml deploy/alertmanager/alertmanager.yml || true
    cp deploy/prometheus/prometheus.default.yml deploy/prometheus/prometheus.yml || true
    cp deploy/supervisor/supervisord.default.conf deploy/supervisor/supervisord.conf || true
fi

