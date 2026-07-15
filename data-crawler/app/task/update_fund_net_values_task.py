#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金净值更新任务

每30分钟执行一次（task_schedule cron `*/30 * * * *`）：
1. 爬取所有基金的最新净值，批量更新 fund_info
2. 净值更新后检查定投计划：对启用中的定投计划，若当天命中规则且当天能取到净值
   （仅交易日），自动插入一条当天 PENDING 买入流水，由 calculate_buyer_shares_task
   计算份额。幂等由 fund_buyer.uk_fund_code_time 唯一键保证（同基金同天只一条）。
"""

from datetime import datetime

from ..parser import FundParser
from ..storage import FundInfoStorage, FundNavHistoryStorage, FundDipPlanStorage, FundBuyerStorage
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from ..utils.nav_utils import get_nav_value_by_date
from ..utils.dip_utils import should_dip_today


def update_fund_net_values_task(force_run: bool = False):
    """
    基金净值更新任务

    Args:
        force_run: 强制运行参数（该任务不需要时间检查，直接执行）
    """
    logger.info("=" * 50)
    logger.info("开始执行基金净值更新任务")

    parser = FundParser()
    storage = FundInfoStorage()
    nav_history_storage = FundNavHistoryStorage()

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

        # 净值更新后检查定投计划，命中当天且当天有净值则自动插入买入流水
        _process_dip_plans(storage, nav_history_storage)

    except Exception as e:
        logger.error(f"基金净值更新任务异常: {e}")
    finally:
        pass


def _process_dip_plans(fund_info_storage: FundInfoStorage,
                       nav_history_storage: FundNavHistoryStorage) -> None:
    """检查所有启用定投计划，命中当天且当天有净值则插入当天 PENDING 买入流水。

    「仅交易日」约束通过 get_nav_value_by_date 天然实现：非交易日 fund_info 无当日净值、
    fund_nav_history 也无当日记录，返回 None 即跳过，不插入流水。

    多计划命中同一天的处理：fund_buyer 有唯一键 uk_fund_code_time（同基金同天只一条），
    而一个基金可配多条定投计划（如 weekly 周三 + monthly 15号，15号恰逢周三时都命中）。
    因此先按 fund_code 聚合当天命中的所有计划、金额求和，每基金只插一条流水
    （policy/remark 列出所有命中计划 id），避免第二条因唯一键冲突被丢弃、金额漏投。

    幂等由 fund_buyer.uk_fund_code_time 唯一键保证：当天已手动录入买入则
    create_buyer 因唯一键冲突失败，视为"已存在"跳过，不报错。
    """
    dip_storage = FundDipPlanStorage()
    buyer_storage = FundBuyerStorage()

    today = get_beijing_now().date()
    today_str = today.strftime('%Y-%m-%d')

    try:
        plans = dip_storage.get_enabled_plans()
        if not plans:
            return

        logger.info(f"检查 {len(plans)} 条启用定投计划，当天 {today_str}")

        # 1. 筛出当天命中的计划
        hit_plans = [p for p in plans if should_dip_today(p['dip_frequency'], p['dip_day'], today)]
        if not hit_plans:
            return

        # 2. 按 fund_code 聚合：同基金多条命中计划金额求和，避免唯一键冲突丢金额
        grouped = {}
        for p in hit_plans:
            fc = p['fund_code']
            if fc not in grouped:
                grouped[fc] = {
                    'fund_code': fc,
                    'fund_name': p['fund_name'],
                    'total_amount': 0.0,
                    'plan_ids': [],
                }
            grouped[fc]['total_amount'] += float(p['dip_amount'])
            grouped[fc]['plan_ids'].append(p['id'])

        # 3. 逐基金检查当天有无净值（仅交易日）并插入流水
        hit_count = 0
        skip_no_nav = 0
        skip_exists = 0
        for fc, g in grouped.items():
            # 仅交易日：当天能取到净值才插入（非交易日取不到净值跳过）
            nav = get_nav_value_by_date(fund_info_storage, nav_history_storage, fc, today_str)
            if nav is None or nav <= 0:
                skip_no_nav += 1
                logger.info(f"定投 基金 {fc} 当天无净值（非交易日），跳过")
                continue

            plan_ids_str = ','.join(str(pid) for pid in g['plan_ids'])
            ok = buyer_storage.create_buyer({
                'fund_code': fc,
                'fund_name': g['fund_name'],
                'time': today_str,
                'amt': g['total_amount'],
                'type': '2',  # 2: 定投买入（区别于 1 手工买入）
                'policy': f'定投计划#{plan_ids_str}',
                'buy_status': 'PENDING',
                'remark': f'定投自动买入 计划#{plan_ids_str} 共 {g["total_amount"]:.2f}元',
                'create_by': 'dip_task',
            })

            if ok:
                hit_count += 1
                logger.info(
                    f"定投命中: 基金 {fc}({g['fund_name']}) 计划#{plan_ids_str} "
                    f"金额 {g['total_amount']:.2f}，已插入当天买入流水"
                )
            else:
                # create_buyer 返回 False：多为唯一键冲突（当天已存在买入），视为幂等跳过；
                # 也可能是其它异常（create_buyer 内部已记 ERROR 日志），这里记 WARNING 便于排查
                skip_exists += 1
                logger.warning(
                    f"定投 基金 {fc} 插入买入流水失败（可能当天已存在买入或插入异常），跳过"
                )

        logger.info(f"定投检查完成: 命中插入 {hit_count} 条, 无净值跳过 {skip_no_nav} 条, 已存在跳过 {skip_exists} 条")

    except Exception as e:
        logger.error(f"定投计划检查异常: {e}")
