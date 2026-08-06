#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务注册模块

指数抓取任务说明：
- 4 个 task_func 名（fetch_index_task_000688 / _000698 / _000300 / _399673），
  每个 task_func 在 DB 中独立，APScheduler add_job 不互相覆盖，func_args 查询可精确定位。
- 实际逻辑统一调 fetch_index_task(index_code, market, force_run)，根据 task_func 后缀解析 index_code。
"""

from ..utils.logger import logger

# 指数抓取任务的 task_func 后缀 -> (指数代码, 市场)
# 新增指数：在此加一行 + 在 task_schedule 表 INSERT 对应 task_func
INDEX_TASK_REGISTRY = {
    '000688': ('000688', 'sh'),  # 科创 50
    '000698': ('000698', 'sh'),  # 科创 100
    '000300': ('000300', 'sh'),  # 沪深 300
    '399673': ('399673', 'sz'),  # 创业板 50
}


def register_all_tasks(scheduler):
    """
    注册所有任务到调度器

    Args:
        scheduler: CronTaskScheduler 实例
    """
    from .update_fund_net_values_task import update_fund_net_values_task
    from .fetch_index_task import fetch_index_task
    from .fetch_all_indexes_task import fetch_all_indexes_task
    from .backup_fund_nav_history_task import backup_fund_nav_history_task
    from .calculate_buyer_shares_task import calculate_buyer_shares_task
    from .calculate_seller_amount_task import calculate_seller_amount_task
    from .backup_position_snapshot_task import backup_position_snapshot_task
    from .fetch_fund_detail_task import fetch_fund_detail_task

    logger.info("开始注册任务...")

    scheduler.register_task('update_fund_net_values_task', update_fund_net_values_task)
    logger.info("任务 [基金净值更新任务] 已注册")

    # 动态注册 4 个指数抓取 wrapper（按 INDEX_TASK_REGISTRY）
    # 默认参数固化 code / market 避免闭包陷阱
    def make_wrapper(code: str, market: str):
        def wrapper(force_run: bool = False, **_unused):
            return fetch_index_task(force_run=force_run, index_code=code, market=market)
        return wrapper

    for index_code in INDEX_TASK_REGISTRY:
        task_func_name = f'fetch_index_task_{index_code}'
        scheduler.register_task(task_func_name, make_wrapper(index_code, _market_for(index_code)))
        logger.info(f"任务 [{task_func_name}] 已注册")

    scheduler.register_task('fetch_all_indexes_task', fetch_all_indexes_task)
    logger.info("任务 [统一指数遍历抓取任务] 已注册")

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


def _market_for(index_code: str) -> str:
    """根据 index_code 返回市场前缀（来自 INDEX_TASK_REGISTRY）"""
    return INDEX_TASK_REGISTRY.get(index_code, (index_code, 'sh'))[1]
