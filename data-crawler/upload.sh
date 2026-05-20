#!/bin/bash

# Fund Crawler 上传脚本
# 确保只上传必需的文件

set -e

echo "=========================================="
echo "  Fund Crawler 上传脚本"
echo "=========================================="

# 服务器配置
SERVER="root@117.72.53.38"
REMOTE_PATH="/opt/data-crawler"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "本地目录: $SCRIPT_DIR"
echo "目标服务器: $SERVER"
echo "目标路径: $REMOTE_PATH"
echo ""

# 检查必需文件
REQUIRED_FILES=(
    "Dockerfile"
    "docker-compose.yml"
    "deploy.sh"
    ".env"
    "requirements.txt"
    "setup.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "错误: 缺少必需文件 $file"
        exit 1
    fi
done

echo "检查完成，所有必需文件已准备好"
echo ""

echo "开始上传..."
echo ""

# 使用 rsync 排除不需要的文件（更安全）
if command -v rsync &> /dev/null; then
    echo "使用 rsync 上传..."
    rsync -av \
        --exclude='.git/' \
        --exclude='.gitignore' \
        --exclude='*.pyc' \
        --exclude='__pycache__/' \
        --exclude='venv/' \
        --exclude='.egg-info/' \
        --exclude='build/' \
        --exclude='dist/' \
        . "$SERVER:$REMOTE_PATH"
else
    echo "使用 scp 上传..."
    scp -r \
        app/ \
        Dockerfile \
        docker-compose.yml \
        deploy.sh \
        .env \
        requirements.txt \
        setup.py \
        .dockerignore \
        API_DOC.md \
        "$SERVER:$REMOTE_PATH/"
fi

echo ""
echo "=========================================="
echo "  上传完成！"
echo "=========================================="
echo ""
echo "登录服务器执行部署:"
echo "  ssh $SERVER"
echo "  cd $REMOTE_PATH"
echo "  chmod +x deploy.sh"
echo "  ./deploy.sh"
