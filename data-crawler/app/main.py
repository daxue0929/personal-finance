from .parser import FundParser
from .storage import FundStorage
from .scheduler import create_cron_scheduler
from .web import create_app, start_server_in_background, set_scheduler
from .utils.logger import logger


def update_fund_net_values_task():
    logger.info("=" * 50)
    logger.info("开始执行基金净值更新任务")

    parser = FundParser()
    storage = FundStorage()

    try:
        fund_codes = storage.get_all_fund_codes()
        if not fund_codes:
            logger.warning("数据库中未找到任何基金")
            return

        logger.info(f"从数据库获取到 {len(fund_codes)} 只基金")

        fund_data_list = parser.fetch_multiple_funds(fund_codes)

        if not fund_data_list:
            logger.warning("未获取到任何基金数据")
            return

        logger.info(f"成功获取 {len(fund_data_list)} 只基金的数据")

        result = storage.batch_update_fund_net_values(list(fund_data_list.values()))
        logger.info(f"更新结果: 成功 {result['success']} 条, 失败 {result['failed']} 条")

    except Exception as e:
        logger.error(f"基金净值更新任务异常: {e}")
    finally:
        storage.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='基金数据爬虫')
    parser.add_argument('--port', type=int, default=5000,
                        help='Web服务端口 (默认5000)')
    parser.add_argument('--check-interval', type=int, default=10,
                        help='配置检查间隔秒数 (默认10秒)')

    args = parser.parse_args()

    logger.info(f"启动基金数据爬虫服务，端口 {args.port}")

    scheduler = create_cron_scheduler()
    scheduler.check_interval = args.check_interval
    scheduler.register_task('update_fund_net_values_task', update_fund_net_values_task)
    set_scheduler(scheduler)

    start_server_in_background(port=args.port)
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
