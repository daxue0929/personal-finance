#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创100指数数据抓取任务
"""

import datetime

from ..parser import Kc100IndexParser
from ..storage import FundInfoStorage
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now


def _is_trading_time() -> bool:
    """检查当前是否在交易时间内（周一至周五 9:30-14:55）"""
    now = get_beijing_now()
    
    # 检查是否是工作日（周一到周五）
    if now.weekday() >= 5:
        return False
    
    # 检查时间是否在9:30-14:55之间
    current_time = now.time()
    start_time = datetime.time(9, 30)
    end_time = datetime.time(14, 55)
    
    return start_time <= current_time <= end_time


def fetch_kc100_index_task():
    logger.info("=" * 50)
    logger.info("开始执行科创100指数数据抓取任务")

    # 检查是否在交易时间内
    if not _is_trading_time():
        logger.info("当前不在交易时间内（周一至周五 9:30-14:55），跳过执行")
        return

    parser = Kc100IndexParser()
    storage = FundInfoStorage()

    try:
        index_data = parser.fetch()

        if not index_data:
            logger.warning("未获取到科创100指数数据")
            return

        logger.info(f"成功获取科创100指数数据:")
        logger.info(f"  指数代码: {index_data.index_code}")
        logger.info(f"  指数名称: {index_data.index_name}")
        logger.info(f"  当前点位: {index_data.current_price}")
        logger.info(f"  涨跌额: {index_data.change:+.4f}")
        logger.info(f"  涨跌幅: {index_data.change_pct:+.2f}%")
        logger.info(f"  成交量: {index_data.volume}")
        logger.info(f"  更新时间: {index_data.update_time}")

        # 将涨跌幅保留两位小数直接存储到 fund_info 表
        change_pct_str = f"{index_data.change_pct:.2f}"
        logger.info(f"  涨跌幅(保留两位小数): {change_pct_str}%")
        
        # 更新 fund_info 表中 020292 的 remark 字段
        success = storage.update_fund_remark('020292', change_pct_str)
        if success:
            logger.info("  成功更新 fund_info 表中 020292 的 remark 字段")
        else:
            logger.warning("  更新 fund_info 表失败")

    except Exception as e:
        logger.error(f"科创100指数数据抓取任务异常: {e}")
    finally:
        storage.close()