#!/bin/bash

# Fund Crawler 一键部署脚本（修复版）
# 处理 Docker 镜像加速器问题

set -e

echo "=========================================="
echo "  Fund Crawler 部署脚本 (修复版)"
echo "=========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

echo "Docker: $(docker --version)"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查配置文件
if [ ! -f ".env" ]; then
    echo "错误: .env 配置文件不存在"
    exit 1
fi

# 修复 Docker 配置（临时移除镜像加速器）
DOCKER_CONFIG="/etc/docker/daemon.json"
BACKUP_FILE="/etc/docker/daemon.json.backup"

if [ -f "$DOCKER_CONFIG" ]; then
    echo "[1/4] 检测到 Docker 配置文件，备份并修复..."
    cp "$DOCKER_CONFIG" "$BACKUP_FILE"
    echo "{\"log-driver\": \"json-file\", \"log-opts\": {\"max-size\": \"10m\"}}" > "$DOCKER_CONFIG"
    systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || true
    sleep 5
else
    echo "[1/4] Docker 配置文件不存在，跳过修复..."
fi

echo "[2/4] 手动拉取 Python 基础镜像..."
docker pull python:3.12-slim

echo "[3/4] 构建应用镜像..."
docker build -t fund-crawler .

echo "[4/4] 启动服务..."
docker-compose up -d

# 恢复 Docker 配置
if [ -f "$BACKUP_FILE" ]; then
    echo ""
    echo "是否恢复原来的 Docker 配置? [y/N]"
    read -r response
    if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
        echo "恢复 Docker 配置..."
        cp "$BACKUP_FILE" "$DOCKER_CONFIG"
        systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || true
    fi
fi

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "服务状态:"
docker-compose ps
echo ""
echo "API 地址: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  重启服务: docker-compose restart"
echo "  停止服务: docker-compose down"
