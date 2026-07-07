"""
调度器进程入口

启动流程：
1. 加载环境变量
2. 启动日志队列消费线程
3. 创建调度器并注册任务
4. 启动调度器（开始按 cron 执行爬虫任务）
5. 启动内部控制 Flask（供 web 进程转发调用）

用法：python -m app.scheduler --port 5001 --check-interval 10
"""
import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .cron_scheduler import create_cron_scheduler
from .control_server import create_control_app
from ..task import register_all_tasks
from ..utils.logger import logger, start_log_queue, stop_log_queue


def main():
    parser = argparse.ArgumentParser(description='基金数据爬虫 - 调度器进程')
    parser.add_argument('--port', type=int, default=5001,
                        help='内部控制服务端口 (默认5001)')
    parser.add_argument('--check-interval', type=int, default=10,
                        help='任务配置检查间隔秒数 (默认10秒)')
    args = parser.parse_args()

    logger.info(f"启动调度器进程，内部控制端口 {args.port}, 检查间隔 {args.check_interval}s")

    # 启动日志队列消费线程（写 system_log 表）
    start_log_queue()

    # 创建并注册调度器
    scheduler = create_cron_scheduler()
    scheduler.check_interval = args.check_interval
    register_all_tasks(scheduler)
    scheduler.start()

    # 启动内部控制 Flask（前台阻塞）
    app = create_control_app(scheduler)
    logger.info("调度器内部控制服务已启动，等待 web 进程连接")
    try:
        app.run(host='0.0.0.0', port=args.port, threaded=True, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭调度器进程")
        scheduler.stop()
        stop_log_queue()


if __name__ == '__main__':
    main()
