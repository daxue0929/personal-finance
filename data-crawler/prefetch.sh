#!/bin/bash

# 预下载所有 docker 基础镜像
# 用法：在 ./deploy.sh 之前手动跑一次，或在 CI/CD / 全新环境初始化时跑
# 已缓存的镜像会秒过（仅 digest 校验），不会重新下载
#
# 与 deploy.sh 的分工：
# - prefetch.sh：只负责下载基础镜像到本地（一次性 / 镜像版本更新时）
# - deploy.sh：构建应用层镜像 + 启停容器，**不再调 docker pull**

set -e

echo "=========================================="
echo "  Fund Crawler 基础镜像预下载"
echo "=========================================="

if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

echo "Docker: $(docker --version)"
echo ""

# 检查 daemon 是否配了国内镜像加速（CN 服务器强烈推荐）
# 没配不阻断（开发机可能不需要），但打 WARN 提示
if [ -f /etc/docker/daemon.json ]; then
    if grep -q "registry-mirrors" /etc/docker/daemon.json; then
        echo "✓ 检测到 Docker registry-mirrors 配置（国内加速已生效）"
    else
        echo "⚠️  /etc/docker/daemon.json 未配置 registry-mirrors"
        echo "   服务器下载会很慢，建议跑: sudo ./setup-docker-mirror.sh"
    fi
else
    echo "⚠️  /etc/docker/daemon.json 不存在"
    echo "   服务器下载会很慢，建议跑: sudo ./setup-docker-mirror.sh"
fi
echo ""

# ---- 应用镜像基础 ----
echo "[1/4] python:3.12-slim (应用镜像基础)..."
docker pull python:3.12-slim

# ---- browser 镜像基础 ----
echo "[2/4] mcr.microsoft.com/playwright:v1.49.1-noble (browser 镜像基础)..."
docker pull mcr.microsoft.com/playwright:v1.49.1-noble

# ---- 验证 ----
echo ""
echo "=========================================="
echo "  预下载完成"
echo "=========================================="
echo ""
echo "本地基础镜像："
docker images --format "  {{.Repository}}:{{.Tag}}\t{{.Size}}" \
    python:3.12-slim \
    mcr.microsoft.com/playwright:v1.49.1-noble
echo ""
echo "下一步：./deploy.sh"
