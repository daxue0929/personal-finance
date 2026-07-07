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

# 主版本号（可手动修改）
MAJOR_VERSION="1.0"

# 获取当前最大的小版本号
function get_next_minor_version {
    # 查找所有以 fund-crawler:${MAJOR_VERSION} 开头的镜像
    local versions=$(docker images --format "{{.Tag}}" fund-crawler 2>/dev/null | grep "^${MAJOR_VERSION}\." | sort -V)
    
    if [ -z "$versions" ]; then
        # 没有找到已存在的版本，从 1 开始
        echo "1"
        return
    fi
    
    # 获取最新的版本号
    local latest_version=$(echo "$versions" | tail -n 1)
    # 提取小版本号（如 1.0.3 中的 3）
    local minor_version=$(echo "$latest_version" | awk -F. '{print $3}')
    
    # 如果小版本号为空或不是数字，从 1 开始
    if ! [[ "$minor_version" =~ ^[0-9]+$ ]]; then
        echo "1"
        return
    fi
    
    # 小版本号加 1
    echo $((minor_version + 1))
}

# 获取下一个版本号
MINOR_VERSION=$(get_next_minor_version)
FULL_VERSION="${MAJOR_VERSION}.${MINOR_VERSION}"

echo "当前版本号: ${FULL_VERSION}"
echo ""

echo "[1/3] 拉取 Python 基础镜像..."
docker pull python:3.12-slim

echo "[2/3] 构建应用镜像 (版本: ${FULL_VERSION})..."
docker build -t fund-crawler:${FULL_VERSION} -t fund-crawler:latest .

echo "[3/3] 启动服务..."
docker-compose up -d --force-recreate --remove-orphans

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "部署版本: ${FULL_VERSION}"
echo "服务状态:"
docker-compose ps
echo ""
echo "API 地址: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "两个容器："
echo "  fund-crawler-web        对外提供 Web API (端口 5000)"
echo "  fund-crawler-scheduler  调度器 + 爬虫任务 (内部端口 5001，不对外)"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  查看web日志:    docker-compose logs -f web"
echo "  查看调度器日志: docker-compose logs -f scheduler"
echo "  重启服务: docker-compose restart"
echo "  停止服务: docker-compose down"
echo "  查看镜像: docker images fund-crawler"