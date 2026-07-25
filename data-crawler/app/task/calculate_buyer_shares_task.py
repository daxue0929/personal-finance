#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算基金买入份额任务
每小时执行一次，查询待处理的买入记录，根据净值计算份额
"""

from ..storage import FundBuyerStorage, FundInfoStorage, FundNavHistoryStorage
from ..storage.fund_buyer_storage import compute_buyer_shares
from ..utils.logger import logger
from ..utils.nav_utils import get_nav_value_by_date


def calculate_buyer_shares_task(force_run: bool = False):
    """
    计算基金买入份额任务
    
    Args:
        force_run: 强制运行参数（该任务不需要时间检查，直接执行）
    """
    logger.info("=" * 50)
    logger.info("开始执行计算基金买入份额任务")

    buyer_storage = FundBuyerStorage()
    fund_info_storage = FundInfoStorage()
    nav_history_storage = FundNavHistoryStorage()

    try:
        # 获取所有待处理的买入记录（已按时间升序、ID升序排序）
        pending_buyers = buyer_storage.get_pending_buyers()
        
        if not pending_buyers:
            logger.info("没有待处理的买入记录")
            return

        logger.info(f"找到 {len(pending_buyers)} 条待处理的买入记录")

        success_count = 0
        fail_count = 0
        skip_count = 0
        
        # 按 (fund_code, buy_time) 分组存储，用于合并更新持仓
        grouped_buyers = {}

        for buyer in pending_buyers:
            buyer_id = buyer['id']
            fund_code = buyer['fund_code']
            buy_time = buyer['time']
            buy_amt = buyer['amt']

            try:
                # 获取净值
                nav = get_nav_value_by_date(
                    fund_info_storage,
                    nav_history_storage,
                    fund_code,
                    buy_time
                )

                if nav is None or nav <= 0:
                    logger.warning(
                        f"买入记录 {buyer_id}: 基金 {fund_code} 在 {buy_time} "
                        f"无法获取有效净值，跳过"
                    )
                    skip_count += 1
                    continue

                # 计算份额：金额 / 净值，四舍五入保留4位小数
                shares = compute_buyer_shares(buy_amt, nav)

                logger.info(
                    f"买入记录 {buyer_id}: 基金 {fund_code} 在 {buy_time} "
                    f"买入金额 {buy_amt} / 净值 {nav} = 份额 {shares}"
                )

                # 按 (fund_code, buy_time) 分组，用于后续原子化合并更新持仓
                # 注意：此处暂不标记买入 SUCCESS，由 process_buyer_transaction 在原子事务内统一回写，
                # 避免「份额已 SUCCESS 但持仓累加失败」导致永久漏加。
                # success_count 不在此累加，改到事务成功后按 buyer_ids 计数，避免与 fail_count 重复。
                key = f"{fund_code}_{buy_time}"
                if key not in grouped_buyers:
                    grouped_buyers[key] = {
                        'fund_code': fund_code,
                        'buy_time': buy_time,
                        'total_shares': 0.0,
                        'total_amt': 0.0,
                        'nav': nav,
                        'buyer_ids': []
                    }
                grouped_buyers[key]['total_shares'] += float(shares)
                grouped_buyers[key]['total_amt'] += buy_amt
                grouped_buyers[key]['buyer_ids'].append(buyer_id)

            except Exception as e:
                logger.error(f"处理买入记录 {buyer_id} 时发生异常: {e}")
                fail_count += 1

        # 原子化合并更新持仓：同一天同一基金的记录合并后，单事务完成「累加持仓 + 回写买入 SUCCESS」。
        # 幂等由 PENDING 状态机保证（get_pending_buyers 只取 PENDING），不再用 position.buy_date 做日期水位。
        for key, group in grouped_buyers.items():
            result = buyer_storage.process_buyer_transaction(
                group['buyer_ids'],
                group['fund_code'],
                group['total_shares'],
                group['total_amt'],
                group['nav'],
                group['buy_time']
            )
            if result == 'SUCCESS':
                logger.info(
                    f"合并更新持仓: 基金 {group['fund_code']}, 日期 {group['buy_time']}, "
                    f"总份额 {group['total_shares']:.4f}, 总金额 {group['total_amt']}, "
                    f"涉及流水ID: {group['buyer_ids']}"
                )
                success_count += len(group['buyer_ids'])
            elif result == 'NO_POSITION':
                # 无持仓记录：买入已标记 SUCCESS，不计入持仓（与原 _update_position 行为一致）
                logger.info(
                    f"基金 {group['fund_code']} 无持仓记录，仅标记买入 SUCCESS，流水ID: {group['buyer_ids']}"
                )
                success_count += len(group['buyer_ids'])
            else:
                # 'ERROR'：事务回滚，买入保持 PENDING，下次任务重试
                logger.warning(
                    f"合并更新持仓失败（保持 PENDING 待重试）: 基金 {group['fund_code']}, "
                    f"日期 {group['buy_time']}, 流水ID: {group['buyer_ids']}"
                )
                fail_count += len(group['buyer_ids'])

        logger.info(
            f"计算份额任务完成: 成功 {success_count} 条, 失败 {fail_count} 条, "
            f"跳过 {skip_count} 条, 合并更新持仓 {len(grouped_buyers)} 组"
        )

    except Exception as e:
        logger.error(f"计算基金买入份额任务异常: {e}", extra={
            'category': 'task',
            'task_name': 'calculate_buyer_shares_task'
        })
