"""
Web 进程入口

启动流程：
1. 加载环境变量
2. 启动日志队列消费线程
3. 启动 Flask Web 服务（对外提供 API）

注意：web 进程不再持有 scheduler 实例，控制类接口通过 scheduler_proxy 转发到调度器进程。

用法：python -m app.web --port 5000
"""
import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .api_server import start_server
from ..utils.logger import logger, start_log_queue, stop_log_queue


def main():
    parser = argparse.ArgumentParser(description='基金数据爬虫 - Web API 进程')
    parser.add_argument('--port', type=int, default=5000,
                        help='Web 服务端口 (默认5000)')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='启用 debug 模式 (默认关闭)')
    args = parser.parse_args()

    logger.info(f"启动 Web API 进程，端口 {args.port}, debug: {args.debug}")

    # 启动日志队列消费线程（写 system_log 表）
    start_log_queue()

    # 启动 Web 服务（前台阻塞）
    try:
        start_server(port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭 Web 进程")
        stop_log_queue()


if __name__ == '__main__':
    main()
