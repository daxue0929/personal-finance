#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数抓取公共逻辑
交易时段判断 + 拉取腾讯实时行情 + 入库 index_info。
供各指数任务（科创50/100、沪深300、创业板50）复用。
"""

import datetime
from typing import Optional

from ..parser import KcIndexParser
from ..parser.kc_index_parser import KcIndexData
from ..storage import IndexInfoStorage
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now


def is_trading_time() -> bool:
    """是否在交易时段（周一至周五 9:00-15:05）"""
    now = get_beijing_now()
    if now.weekday() >= 5:
        return False
    return datetime.time(9, 0) <= now.time() <= datetime.time(15, 5)


def fetch_and_store_index(index_code: str, force_run: bool = False) -> Optional[KcIndexData]:
    """拉取指数实时行情并存入 index_info 表。

    Args:
        index_code: 指数代码（须在 KcIndexParser.INDEX_CONFIG 中）
        force_run: True 时跳过交易时段检查

    Returns:
        KcIndexData：成功时；跳过/无数据/异常时返回 None
    """
    if not force_run and not is_trading_time():
        logger.info("当前不在交易时间内（周一至周五 9:00-15:05），跳过执行")
        return None

    parser = KcIndexParser(index_code)
    storage = IndexInfoStorage()
    try:
        index_data = parser.fetch()
        if not index_data:
            logger.warning(f"未获取到指数 {index_code} 数据")
            return None

        logger.info(f"成功获取指数数据: {index_data.index_code} {index_data.index_name} "
                    f"收盘={index_data.close_price} 涨跌幅={index_data.change_percent:+.2f}% "
                    f"PE={index_data.pe_ratio} PB={index_data.pb_ratio}")

        today = get_beijing_now().date()
        trade_date = index_data.trade_date or today.isoformat()
        index_info_data = {
            'index_code': index_data.index_code,
            'index_name': index_data.index_name,
            'index_type': '宽基指数',
            'trade_date': trade_date,
            'open_price': index_data.open_price,
            'close_price': index_data.close_price,
            'high_price': index_data.high_price,
            'low_price': index_data.low_price,
            'change_percent': index_data.change_percent,
            'volume': index_data.volume,
            'amount': index_data.amount,
            'pe_ratio': index_data.pe_ratio,
            'pe_percentile': 0.0,
            'pb_ratio': index_data.pb_ratio,
            'source': '腾讯财经',
        }

        if storage.create_or_update_index_info(index_info_data):
            logger.info(f"  成功更新 index_info 表 (日期: {trade_date})")
        else:
            logger.warning("  更新 index_info 表失败")
        return index_data
    except Exception as e:
        logger.error(f"指数 {index_code} 抓取任务异常: {e}")
        return None
