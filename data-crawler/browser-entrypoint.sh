#!/bin/sh
# browser 服务启动脚本
# 1. 启动 chrome 有头模式（xvfb-run 虚拟显示）监听 127.0.0.1:9223（CDP 端口）
#    有头模式规避东方财富等网站的 headless 检测（headless 下主行情区数字不渲染）
# 2. node HTTP 反向代理把 0.0.0.0:9222 转发到 127.0.0.1:9223：
#    - 改写 Host 头为 127.0.0.1:9223（chrome 131 对 /json/version 有 Host 头检查，
#      拒绝非 localhost 的 Host，如容器间的 browser:9222）
#    - 改写 /json/version 响应里的 webSocketDebuggerUrl（127.0.0.1:9223 -> 请求方 host:9222），
#      使 playwright 连 9222（代理）而非直连 9223
#    - WebSocket 升级经代理转发到 9223
# 3. 代理前台运行，退出则容器退出

set -e

CHROME_BIN=$(ls /ms-playwright/chromium-*/chrome-linux/chrome)

# 1. 启动 chrome（有头模式 + xvfb 虚拟显示，后台，CDP 监听 127.0.0.1:9223）
# --disable-blink-features=AutomationControlled：去掉 navigator.webdriver 标记，
# 规避东方财富等网站的 Playwright/自动化检测（检测到则不渲染行情数据）
xvfb-run -a --server-args="-screen 0 1280x1024x24" "$CHROME_BIN" \
  --no-sandbox \
  --disable-gpu \
  --disable-blink-features=AutomationControlled \
  --window-size=1280,1024 \
  --user-data-dir=/tmp/chrome-profile \
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

# 3. node HTTP 反向代理 0.0.0.0:9222 -> 127.0.0.1:9223（改写 Host 头，前台运行）
echo "node 代理转发 0.0.0.0:9222 -> 127.0.0.1:9223 (改写 Host)"
exec node -e '
const http = require("http");
const net = require("net");
const server = http.createServer((req, res) => {
  const opts = {hostname:"127.0.0.1", port:9223, path:req.url, method:req.method,
                headers:Object.assign({}, req.headers, {host:"127.0.0.1:9223"})};
  const up = http.request(opts, r => {
    // 对 /json/version 等返回 ws endpoint 的响应：把 webSocketDebuggerUrl 的 host:port
    // 从 127.0.0.1:9223 改写成请求方的 host:9222，使 playwright 连 9222（代理）而非直连 9223
    let body = [];
    r.on("data", c => body.push(c));
    r.on("end", () => {
      let buf = Buffer.concat(body);
      const ct = (r.headers["content-type"]||"");
      if (ct.includes("json") && buf.includes("webSocketDebuggerUrl")) {
        const reqHost = (req.headers["x-forwarded-host"] || req.headers["host"] || "127.0.0.1:9222").split(":")[0];
        let text = buf.toString("utf8");
        text = text.replace(/ws:\/\/[^\/]+:9223\//g, "ws://"+reqHost+":9222/");
        buf = Buffer.from(text, "utf8");
        delete r.headers["content-length"];
      }
      res.writeHead(r.statusCode, r.headers);
      res.end(buf);
    });
  });
  up.on("error", e => { res.writeHead(502); res.end("proxy error: "+e.message); });
  req.pipe(up);
});
server.on("upgrade", (req, sock) => {
  // WebSocket 升级：playwright 连 9222，代理转发到 chrome 的 9223，改写 Host
  const up = net.connect({host:"127.0.0.1", port:9223}, () => {
    let head = `${req.method} ${req.url} HTTP/1.1\r\n`;
    for (const [k,v] of Object.entries(req.headers)) {
      head += (k.toLowerCase()==="host" ? "host: 127.0.0.1:9223" : `${k}: ${v}`) + "\r\n";
    }
    head += "\r\n";
    up.write(head);
    sock.pipe(up); up.pipe(sock);
  });
  up.on("error", () => sock.end());
});
server.listen(9222, "0.0.0.0", () => console.log("代理监听 0.0.0.0:9222"));
'
