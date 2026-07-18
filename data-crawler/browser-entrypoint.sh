#!/bin/sh
# browser 服务启动脚本
# 1. 启动 chrome headless 监听 127.0.0.1:9223（CDP 端口，chrome 只绑 loopback）
# 2. socat 把 0.0.0.0:9222 转发到 127.0.0.1:9223，使容器外可访问 CDP
# 3. 等 chrome 就绪后 socat 退出时一并退出

set -e

CHROME_BIN=$(ls /ms-playwright/chromium-*/chrome-linux/chrome)

# 1. 启动 chrome（后台，CDP 监听 127.0.0.1:9223）
"$CHROME_BIN" \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --remote-debugging-port=9223 \
  --remote-debugging-address=127.0.0.1 &

CHROME_PID=$!

# 2. 等 chrome 的 9223 就绪（最多等 15 秒）
echo "等待 chrome 就绪..."
for i in $(seq 1 30); do
  if node -e "require('http').get('http://127.0.0.1:9223/json/version',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))" 2>/dev/null; then
    echo "chrome 已就绪 (127.0.0.1:9223)"
    break
  fi
  sleep 0.5
done

# 3. socat 转发 0.0.0.0:9222 -> 127.0.0.1:9223（前台运行，socat 退出则容器退出）
echo "socat 转发 0.0.0.0:9222 -> 127.0.0.1:9223"
exec socat TCP-LISTEN:9222,fork,reuseaddr TCP:127.0.0.1:9223
