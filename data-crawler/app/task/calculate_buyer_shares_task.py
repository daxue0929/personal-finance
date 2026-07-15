#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算基金买入份额任务
每小时执行一次，查询待处理的买入记录，根据净值计算份额
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from ..storage import FundBuyerStorage, FundInfoStorage, FundNavHistoryStorage
from ..storage.position_storage import PositionStorage
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
    position_storage = PositionStorage()

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
                shares = Decimal(str(buy_amt)) / Decimal(str(nav))
                shares = shares.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                # 更新份额和状态
                if buyer_storage.update_buyer_shares(buyer_id, float(shares), 'SUCCESS'):
                    logger.info(
                        f"买入记录 {buyer_id}: 基金 {fund_code} 在 {buy_time} "
                        f"买入金额 {buy_amt} / 净值 {nav} = 份额 {shares}"
                    )
                    success_count += 1
                    
                    # 按 (fund_code, buy_time) 分组，用于后续合并更新持仓
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
                else:
                    fail_count += 1

            except Exception as e:
                logger.error(f"处理买入记录 {buyer_id} 时发生异常: {e}")
                fail_count += 1

        # 合并更新持仓：同一天同一基金的记录合并后只更新一次持仓
        for key, group in grouped_buyers.items():
            _update_position(
                position_storage,
                group['fund_code'],
                group['total_shares'],
                group['nav'],
                group['buy_time'],
                group['total_amt']
            )
            logger.info(
                f"合并更新持仓: 基金 {group['fund_code']}, 日期 {group['buy_time']}, "
                f"总份额 {group['total_shares']:.4f}, 总金额 {group['total_amt']}, "
                f"涉及流水ID: {group['buyer_ids']}"
            )

        logger.info(
            f"计算份额任务完成: 成功 {success_count} 条, 失败 {fail_count} 条, "
            f"跳过 {skip_count} 条, 合并更新持仓 {len(grouped_buyers)} 组"
        )

    except Exception as e:
        logger.error(f"计算基金买入份额任务异常: {e}", extra={
            'category': 'task',
            'task_name': 'calculate_buyer_shares_task'
        })


def _update_position(position_storage, fund_code: str, new_shares: float, cost_price: float, buy_date: str, buy_amt: float) -> bool:
    """
    更新基金持仓数据
    
    只有当买入流水的买入日期大于持仓的买入日期时，才更新持仓数据（避免历史数据重复计算）。
    
    Args:
        position_storage: 持仓存储实例
        fund_code: 基金代码
        new_shares: 新买入份额
        cost_price: 本次买入净值（成本价，同时用于更新当前净值）
        buy_date: 本次买入日期
        buy_amt: 本次买入金额（直接从流水传入，避免浮点精度问题）
    
    Returns:
        True/False
    """
    try:
        # 查询该基金的持仓记录
        position = position_storage.get_position_by_fund_code(fund_code)
        
        if not position:
            logger.info(f"基金 {fund_code} 没有持仓记录，跳过更新")
            return True
        
        position_id = position['id']
        position_buy_date = position.get('buy_date')
        
        # 检查买入日期：只有流水的买入日期大于持仓的买入日期才更新
        if position_buy_date:
            try:
                pos_date = datetime.strptime(position_buy_date, '%Y-%m-%d')
                buyer_date = datetime.strptime(buy_date, '%Y-%m-%d')
                
                if buyer_date <= pos_date:
                    logger.info(
                        f"持仓 {position_id}: 流水买入日期 {buy_date} <= 持仓买入日期 {position_buy_date}, "
                        f"跳过更新（避免历史数据重复计算）"
                    )
                    return True
            except Exception as e:
                logger.warning(f"日期比较异常: {e}, 继续更新")
        
        # 使用计算份额时获取到的净值作为当前净值
        current_price = cost_price
        
        # 更新持仓数据（累加份额，重新计算成本价）
        result = position_storage.update_position_by_buyer(
            position_id,
            new_shares,
            cost_price,
            buy_date,
            buy_amt,
            current_price
        )
        
        if result:
            logger.info(
                f"持仓 {position_id} 更新成功: 基金 {fund_code}, "
                f"新份额 {new_shares}, 成本价 {cost_price}, 当前净值 {current_price:.4f}, 买入日期 {buy_date}"
            )
        else:
            logger.warning(f"持仓 {position_id} 更新失败")
        
        return result
        
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        return False
