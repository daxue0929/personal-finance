#!/bin/bash

# Fund Crawler 一键部署脚本

set -e

echo "=========================================="
echo "  Fund Crawler 一键部署脚本"
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

echo "[1/3] 拉取 Python 基础镜像..."
docker pull python:3.12-slim

echo "[2/3] 构建应用镜像..."
docker build -t fund-crawler .

echo "[3/3] 启动服务..."
docker-compose up -d

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
