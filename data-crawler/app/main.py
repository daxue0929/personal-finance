from .scheduler import create_cron_scheduler
from .web import create_app, start_server_in_background, set_scheduler
from .task import register_all_tasks
from .utils.logger import logger


def main():
    import argparse

    parser = argparse.ArgumentParser(description='基金数据爬虫')
    parser.add_argument('--port', type=int, default=5000,
                        help='Web服务端口 (默认5000)')
    parser.add_argument('--check-interval', type=int, default=10,
                        help='配置检查间隔秒数 (默认10秒)')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='启用debug模式 (默认关闭)')

    args = parser.parse_args()

    logger.info(f"启动基金数据爬虫服务，端口 {args.port}, debug: {args.debug}")

    scheduler = create_cron_scheduler()
    scheduler.check_interval = args.check_interval
    register_all_tasks(scheduler)
    set_scheduler(scheduler)

    start_server_in_background(port=args.port, debug=args.debug)
    scheduler.start()

    logger.info("服务已启动，按 Ctrl+C 停止")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        scheduler.stop()


if __name__ == '__main__':
    main()
