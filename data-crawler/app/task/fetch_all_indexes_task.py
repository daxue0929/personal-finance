#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一指数遍历抓取任务

替代 4 条老 fetch_index_task_<code>（PR 8d939f2 + 本次重构后保留作回滚通道）。
遍历 index_basic.enabled=1 全量拉取，新指数只需在 DB 加行 + enabled=1，**不需改代码**。

设计要点：
- ThreadPoolExecutor(max_workers=4) 并发：4 支指数 ≤1s 完成
- 单支异常隔离：每 future 包 try/except，失败不影响其他
- kc100 (000698) 副作用：抓取后调 FundInfoStorage.update_fund_remark('020292', ...)，
  **在 as_completed 收集完成后单线程触发**（避免多线程竞争）
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..storage import IndexBasicStorage, FundInfoStorage
from ..utils.logger import logger
from .index_fetch_helper import fetch_and_store_index_with_market


# TODO: linked_fund_code / linked_field 字段后续加入 index_basic 后可数据驱动化；
# 详见 PRD "index-basic-table" §5 非目标。当前 kc100 → 020292 联动仍硬编码。
_KC100_FUND_CODE = '020292'
_KC100_INDEX_CODE = '000698'


def fetch_all_indexes_task(force_run: bool = False) -> None:
    """遍历 index_basic.enabled=1 全量抓取。

    Args:
        force_run: 透传给 fetch_and_store_index_with_market；True 时跳过交易时段检查。
    """
    logger.info("=" * 50)
    logger.info("开始执行统一指数遍历抓取任务")

    try:
        enabled = IndexBasicStorage().list_enabled()
    except Exception as e:
        logger.error(f"读取 index_basic 启用列表失败: {e}")
        return

    if not enabled:
        logger.warning("无启用指数（index_basic.enabled=1 为空），跳过本次执行")
        return

    logger.info(f"共 {len(enabled)} 支指数待抓取，并发数 max_workers=4")

    results = []  # 收集成功的 KcIndexData，单线程后续处理 kc100 副作用

    # 并发抓取：每支异常隔离
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_meta = {}
        for code, market, _name in enabled:
            future = executor.submit(
                _fetch_one_safe, code, market, force_run
            )
            future_to_meta[future] = code

        for future in as_completed(future_to_meta):
            code = future_to_meta[future]
            try:
                data = future.result()
                if data is not None:
                    results.append(data)
            except Exception as e:
                logger.error(f"指数 {code} 抓取 future 异常（已在内部 try/except 吞咽）: {e}")

    # 单线程处理 kc100 副作用（避免并发竞争 update_fund_remark）
    for data in results:
        if data.index_code == _KC100_INDEX_CODE:
            try:
                change_pct_str = f"{data.change_percent:.2f}"
                if FundInfoStorage().update_fund_remark(_KC100_FUND_CODE, change_pct_str):
                    logger.info(f"  成功更新 fund_info 表 {_KC100_FUND_CODE} remark 字段 ({change_pct_str}%)")
                else:
                    logger.warning(f"  更新 fund_info 表 {_KC100_FUND_CODE} 失败")
            except Exception as e:
                logger.error(f"更新 fund_info {_KC100_FUND_CODE} remark 失败: {e}")

    logger.info(f"统一指数遍历抓取任务完成：成功 {len(results)}/{len(enabled)} 支")


def _fetch_one_safe(code: str, market: str, force_run: bool):
    """单支抓取的 try/except wrapper，确保 ThreadPoolExecutor 不会因异常污染其他 future。"""
    try:
        return fetch_and_store_index_with_market(code, market, force_run)
    except Exception as e:
        logger.error(f"指数 {code} 抓取异常: {e}")
        return None
