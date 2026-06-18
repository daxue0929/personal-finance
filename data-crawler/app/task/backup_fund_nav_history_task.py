#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金净值历史备份任务
"""

from ..storage import FundNavHistoryStorage
from ..utils.logger import logger


def backup_fund_nav_history_task(force_run: bool = False):
    """
    基金净值历史备份任务
    
    调用存储过程将昨天的基金净值数据备份到历史表中
    
    Args:
        force_run: 强制运行参数
    """
    logger.info("=" * 50)
    logger.info("开始执行基金净值历史备份任务")

    storage = FundNavHistoryStorage()

    try:
        result = storage.backup_nav_history()
        logger.info(f"基金净值历史备份任务完成，成功备份 {result} 条记录")

    except Exception as e:
        logger.error(f"基金净值历史备份任务异常: {e}")
