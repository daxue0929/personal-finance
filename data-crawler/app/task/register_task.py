#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务注册模块
"""

from ..utils.logger import logger


def register_all_tasks(scheduler):
    """
    注册所有任务到调度器

    Args:
        scheduler: CronTaskScheduler 实例
    """
    from .update_fund_net_values_task import update_fund_net_values_task
    from .fetch_kc100_index_task import fetch_kc100_index_task
    from .fetch_kc50_index_task import fetch_kc50_index_task
    from .fetch_hs300_index_task import fetch_hs300_index_task
    from .fetch_cyb50_index_task import fetch_cyb50_index_task
    from .backup_fund_nav_history_task import backup_fund_nav_history_task
    from .calculate_buyer_shares_task import calculate_buyer_shares_task
    from .calculate_seller_amount_task import calculate_seller_amount_task
    from .backup_position_snapshot_task import backup_position_snapshot_task
    from .fetch_fund_detail_task import fetch_fund_detail_task

    logger.info("开始注册任务...")

    scheduler.register_task('update_fund_net_values_task', update_fund_net_values_task)
    logger.info("任务 [基金净值更新任务] 已注册")

    scheduler.register_task('fetch_kc100_index_task', fetch_kc100_index_task)
    logger.info("任务 [科创100指数抓取任务] 已注册")

    scheduler.register_task('fetch_kc50_index_task', fetch_kc50_index_task)
    logger.info("任务 [科创50指数抓取任务] 已注册")

    scheduler.register_task('fetch_hs300_index_task', fetch_hs300_index_task)
    logger.info("任务 [沪深300指数抓取任务] 已注册")

    scheduler.register_task('fetch_cyb50_index_task', fetch_cyb50_index_task)
    logger.info("任务 [创业板50指数抓取任务] 已注册")

    scheduler.register_task('backup_fund_nav_history_task', backup_fund_nav_history_task)
    logger.info("任务 [基金净值历史备份任务] 已注册")

    scheduler.register_task('calculate_buyer_shares_task', calculate_buyer_shares_task)
    logger.info("任务 [计算基金买入份额任务] 已注册")

    scheduler.register_task('calculate_seller_amount_task', calculate_seller_amount_task)
    logger.info("任务 [计算基金卖出金额任务] 已注册")

    scheduler.register_task('backup_position_snapshot_task', backup_position_snapshot_task)
    logger.info("任务 [持仓每日快照备份任务] 已注册")

    scheduler.register_task('fetch_fund_detail_task', fetch_fund_detail_task)
    logger.info("任务 [基金详情网页抓取任务] 已注册")

    logger.info("所有任务注册完成")
