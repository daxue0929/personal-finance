#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创100指数数据抓取任务
指数代码: 000698
每分钟执行一次，实时更新当天数据
额外：更新 fund_info 表中 020292 的 remark 为当日涨跌幅
"""

from .index_fetch_helper import fetch_and_store_index
from ..storage import FundInfoStorage
from ..utils.logger import logger


def fetch_kc100_index_task(force_run: bool = False):
    logger.info("=" * 50)
    logger.info("开始执行科创100指数数据抓取任务")

    index_data = fetch_and_store_index('000698', force_run)
    if not index_data:
        return

    # 副作用：更新 fund_info 表中 020292 的 remark 为涨跌幅（保留两位小数）
    try:
        fund_storage = FundInfoStorage()
        change_pct_str = f"{index_data.change_percent:.2f}"
        if fund_storage.update_fund_remark('020292', change_pct_str):
            logger.info(f"  成功更新 fund_info 表中 020292 的 remark 字段 ({change_pct_str}%)")
        else:
            logger.warning("  更新 fund_info 表失败")
    except Exception as e:
        logger.error(f"更新 fund_info 020292 remark 失败: {e}")
