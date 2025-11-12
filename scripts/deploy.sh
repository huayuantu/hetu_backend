#!/bin/bash
# 部署脚本 - 用于在部署机器上手动部署或作为 CI/CD 的补充

set -e

# 配置变量
REGISTRY="${REGISTRY:-crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com}"
IMAGE_NAME="${IMAGE_NAME:-hetu_xinhong/hetu-backend}"
VERSION="${HETU_VERSION:-latest}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/hetu-backend}"

# 导出环境变量供 docker-compose 使用
export REGISTRY
export IMAGE_NAME
export HETU_VERSION="$VERSION"

echo "=========================================="
echo "Hetu Backend Deployment Script"
echo "=========================================="
echo "Registry: $REGISTRY"
echo "Image: $IMAGE_NAME"
echo "Version: $VERSION"
echo "Deploy Path: $DEPLOY_PATH"
echo "=========================================="

cd "$DEPLOY_PATH"

# 检查 docker-compose.prod.yml 是否存在
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "Error: docker-compose.prod.yml not found in $DEPLOY_PATH"
    exit 1
fi

# 检查 .env 文件是否存在
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Please ensure environment variables are configured."
fi

# 拉取镜像
echo "Pulling images..."
docker pull "$REGISTRY/$IMAGE_NAME:$VERSION-base"
docker pull "$REGISTRY/$IMAGE_NAME:$VERSION-collector"

# 更新服务
echo "Updating services..."
export HETU_VERSION="$VERSION"
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --no-deps api collector

# 等待服务健康检查
echo "Waiting for services to be healthy..."
sleep 10

# 检查服务状态
echo "Service status:"
docker-compose -f docker-compose.prod.yml ps

echo "=========================================="
echo "Deployment completed!"
echo "=========================================="

