#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金净值更新任务
"""

from ..parser import FundParser
from ..storage import FundInfoStorage
from ..utils.logger import logger


def update_fund_net_values_task():
    logger.info("=" * 50)
    logger.info("开始执行基金净值更新任务")

    parser = FundParser()
    storage = FundInfoStorage()

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