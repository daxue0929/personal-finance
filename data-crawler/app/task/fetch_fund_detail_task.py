#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金详情(fundf10)网页抓取任务

用 FundWebParser(Playwright 版)抓取东方财富 fundf10 基本概况页，打印结构化数据。
骨架阶段不落库（用户决策），落库留后续。

触发方式：注册到 register_task 的 task_registry，复用 /api/task/run/fetch_fund_detail_task
手动触发；**不**往 task_schedule 表插行，故不被 cron 调度。
"""

from ..parser import FundWebParser
from ..storage import FundInfoStorage
from ..utils.logger import logger


def _get_fund_codes():
    """从 fund_info 表读取所有有效基金代码（独立函数便于测试 mock）

    FundInfoStorage 每个方法内部各自管理 session（try/finally session.close()），
    无需外层 close（FundInfoStorage 未定义 close 方法）。
    """
    storage = FundInfoStorage()
    try:
        return storage.get_all_fund_codes()
    except Exception as e:
        logger.error(f"读取基金代码列表失败: {e}")
        return []


def fetch_fund_detail_task(force_run: bool = False):
    """抓取所有基金的 fundf10 基本概况并打印结构化数据。

    Args:
        force_run: 强制执行（骨架阶段无交易时间门控，保留参数与其它 task 一致）
    """
    logger.info("=" * 50)
    logger.info("开始执行基金详情(fundf10)网页抓取任务")

    fund_codes = _get_fund_codes()
    if not fund_codes:
        logger.warning("无可抓取的基金代码，跳过执行")
        return

    parser = FundWebParser()
    success_count = 0
    fail_count = 0

    for code in fund_codes:
        try:
            data = parser.fetch(code)
            if data is None:
                logger.warning(f"基金 {code} 抓取失败或无数据")
                fail_count += 1
                continue

            logger.info(f"基金 {code} 抓取成功:")
            logger.info(f"  基金简称: {data.fund_name}")
            logger.info(f"  基金类型: {data.fund_type}")
            logger.info(f"  成立日期: {data.establish_date}")
            logger.info(f"  基金经理: {data.fund_manager}")
            logger.info(f"  净资产规模(亿元): {data.fund_size}")
            success_count += 1
        except Exception as e:
            logger.error(f"基金 {code} 抓取异常: {e}")
            fail_count += 1
            continue  # 单只失败不中断整体

    logger.info(f"基金详情抓取完成: 成功 {success_count} 只, 失败 {fail_count} 只")
