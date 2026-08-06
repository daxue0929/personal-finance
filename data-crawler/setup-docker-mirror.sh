#!/bin/bash

# Docker 国内镜像加速配置（一次性，幂等）
# 解决服务器拉 docker.io 镜像慢的问题
#
# 适用：CentOS / Ubuntu / Debian 等 systemd 系 Linux + Docker daemon
# 作用：把 Docker Hub 流量走国内镜像（腾讯云 + 网易），下载速度 5-10x 提升
# 不适用：mcr.microsoft.com 等其他 registry（需要另寻方案，详见脚本末尾注释）
#
# 跑法：sudo ./setup-docker-mirror.sh
# 已配置过的服务器重跑是安全的（不覆盖用户自定义的其他配置项）

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "错误: 请用 root 或 sudo 跑（需要改 /etc/docker/daemon.json 和重启 docker）"
    echo "  sudo $0"
    exit 1
fi

DAEMON_JSON="/etc/docker/daemon.json"
BACKUP="/etc/docker/daemon.json.bak.$(date +%Y%m%d%H%M%S)"

echo "=========================================="
echo "  Docker 国内镜像加速配置"
echo "=========================================="

# 1. 备份现有配置（如果有）
if [ -f "$DAEMON_JSON" ]; then
    echo "[1/4] 备份现有 $DAEMON_JSON -> $BACKUP"
    cp "$DAEMON_JSON" "$BACKUP"
    HAS_EXISTING=1
else
    echo "[1/4] 现有 $DAEMON_JSON 不存在，跳过备份"
    HAS_EXISTING=0
fi

# 2. 写入新配置
echo "[2/4] 写入 $DAEMON_JSON..."

if [ "$HAS_EXISTING" = "1" ]; then
    # 合并：保留现有字段（log-driver / log-opts / data-root 等），只覆盖 registry-mirrors 和 max-concurrent-downloads
    python3 -c "
import json
with open('$DAEMON_JSON', 'r') as f:
    cfg = json.load(f)
cfg['registry-mirrors'] = [
    'https://mirror.ccs.tencentyun.com',
    'https://hub-mirror.c.163.com'
]
cfg['max-concurrent-downloads'] = 10
with open('$DAEMON_JSON', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
"
else
    cat > "$DAEMON_JSON" <<'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://hub-mirror.c.163.com"
  ],
  "max-concurrent-downloads": 10
}
EOF
fi

echo "  新配置："
cat "$DAEMON_JSON"

# 3. 重启 Docker daemon
echo "[3/4] 重启 Docker daemon..."
if command -v systemctl &> /dev/null; then
    systemctl daemon-reload
    systemctl restart docker
    echo "  systemctl restart docker OK"
elif command -v service &> /dev/null; then
    service docker restart
    echo "  service docker restart OK"
else
    echo "  警告: 未找到 systemctl/service，请手动重启 docker"
    exit 1
fi

# 等 Docker 起来
sleep 3

# 4. 验证
echo "[4/4] 验证配置生效..."
if docker info 2>/dev/null | grep -q "Registry Mirrors"; then
    echo "  ✅ 镜像加速已生效："
    docker info 2>/dev/null | grep -A 4 "Registry Mirrors"
else
    echo "  ❌ 镜像加速未生效，请检查 daemon.json 和 docker 重启日志"
    echo "     journalctl -u docker -n 50"
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✅ 配置完成"
echo "=========================================="
echo ""
echo "下一步："
echo "  cd /path/to/personal-finance/data-crawler"
echo "  ./prefetch.sh     # 拉基础镜像到本地（现在应该快 5-10x）"
echo ""
echo "⚠️  mcr.microsoft.com 镜像加速无效："
echo "  - 微软 registry 没有国内镜像源"
echo "  - 解决：CN 代理 / Mac 拉好 save 传上来 / 改用 docker.io/microsoft/playwright tag"
echo "  - 详见 docs/deployment.md"
