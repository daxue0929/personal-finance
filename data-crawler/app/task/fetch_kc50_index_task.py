#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创50指数数据抓取任务
指数代码: 000688
每分钟执行一次，实时更新当天数据
"""

import datetime

from ..parser import KcIndexParser
from ..storage import IndexInfoStorage
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now


def _is_trading_time() -> bool:
    """检查当前是否在交易时间内（周一至周五 9:00-15:05）"""
    now = get_beijing_now()

    if now.weekday() >= 5:
        return False

    current_time = now.time()
    start_time = datetime.time(9, 0)
    end_time = datetime.time(15, 5)

    return start_time <= current_time <= end_time


def fetch_kc50_index_task(force_run: bool = False):
    logger.info("=" * 50)
    logger.info("开始执行科创50指数数据抓取任务")

    if not force_run and not _is_trading_time():
        logger.info("当前不在交易时间内（周一至周五 9:00-15:05），跳过执行")
        return

    parser = KcIndexParser('000688')
    storage = IndexInfoStorage()

    try:
        index_data = parser.fetch()

        if not index_data:
            logger.warning("未获取到科创50指数数据")
            return

        logger.info(f"成功获取科创50指数数据:")
        logger.info(f"  指数代码: {index_data.index_code}")
        logger.info(f"  指数名称: {index_data.index_name}")
        logger.info(f"  开盘价: {index_data.open_price}")
        logger.info(f"  收盘价/当前价: {index_data.close_price}")
        logger.info(f"  最高价: {index_data.high_price}")
        logger.info(f"  最低价: {index_data.low_price}")
        logger.info(f"  涨跌幅: {index_data.change_percent:+.2f}%")
        logger.info(f"  成交量: {index_data.volume}")
        logger.info(f"  成交额: {index_data.amount}")
        logger.info(f"  PE(TTM): {index_data.pe_ratio}")
        logger.info(f"  PB: {index_data.pb_ratio}")
        logger.info(f"  更新时间: {index_data.update_time}")

        today = get_beijing_now().date()

        index_info_data = {
            'index_code': index_data.index_code,
            'index_name': index_data.index_name,
            'index_type': '宽基指数',
            'trade_date': today.isoformat(),
            'open_price': index_data.open_price,
            'close_price': index_data.close_price,
            'high_price': index_data.high_price,
            'low_price': index_data.low_price,
            'change_percent': index_data.change_percent,
            'volume': index_data.volume,
            'amount': index_data.amount,
            'pe_ratio': index_data.pe_ratio,
            'pe_percentile': 0.0,
            'pb_ratio': index_data.pb_ratio
        }

        success = storage.create_or_update_index_info(index_info_data)
        if success:
            logger.info(f"  成功更新 index_info 表 (日期: {today})")
        else:
            logger.warning("  更新 index_info 表失败")

    except Exception as e:
        logger.error(f"科创50指数数据抓取任务异常: {e}")
    finally:
        storage.close()
