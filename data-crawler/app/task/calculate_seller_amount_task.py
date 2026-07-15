#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算基金卖出金额任务

与 calculate_buyer_shares_task（计算买入份额任务）对称的反向逻辑：
- 买入：金额 ÷ 净值 = 份额
- 卖出：份额 × 净值 = 金额

每小时执行一次，查询待处理（PENDING）的卖出记录，按卖出当日净值计算：
1. 卖出金额 amt = shares × nav（不扣手续费）
2. 已实现盈亏 realized_profit = (nav - 持仓成本价) × shares
3. 原子化扣减基金持仓 + 回写卖出金额/状态（单 session 单 commit，避免重复扣减）
4. 卖出份额超过持仓份额则标记 FAILED，不扣减持仓
"""

from decimal import Decimal, ROUND_HALF_UP

from ..storage import FundSellerStorage, FundInfoStorage, FundNavHistoryStorage
from ..utils.logger import logger
from ..utils.nav_utils import get_nav_value_by_date


def calculate_seller_amount_task(force_run: bool = False):
    """
    计算基金卖出金额任务

    Args:
        force_run: 强制运行参数（该任务不需要时间检查，直接执行）
    """
    logger.info("=" * 50)
    logger.info("开始执行计算基金卖出金额任务")

    seller_storage = FundSellerStorage()
    fund_info_storage = FundInfoStorage()
    nav_history_storage = FundNavHistoryStorage()

    try:
        # 获取所有待处理的卖出记录（已按时间升序、ID升序排序）
        pending_sellers = seller_storage.get_pending_sellers()

        if not pending_sellers:
            logger.info("没有待处理的卖出记录")
            return

        logger.info(f"找到 {len(pending_sellers)} 条待处理的卖出记录")

        success_count = 0
        fail_count = 0
        skip_count = 0

        for seller in pending_sellers:
            seller_id = seller['id']
            fund_code = seller['fund_code']
            sell_time = seller['time']
            sell_shares = seller['shares']

            try:
                # 获取卖出当日净值（与买入侧共用 get_nav_value_by_date，精确日期匹配）
                nav = get_nav_value_by_date(
                    fund_info_storage,
                    nav_history_storage,
                    fund_code,
                    sell_time
                )

                if nav is None or nav <= 0:
                    logger.warning(
                        f"卖出记录 {seller_id}: 基金 {fund_code} 在 {sell_time} "
                        f"无法获取有效净值，跳过（保持 PENDING）"
                    )
                    skip_count += 1
                    continue

                # 卖出金额 = 份额 × 净值，四舍五入保留4位小数
                amt = Decimal(str(sell_shares)) * Decimal(str(nav))
                amt = amt.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                # 原子化处理：扣减持仓 + 回写卖出金额/净值/已实现盈亏/状态（单事务）
                result = seller_storage.process_seller_transaction(
                    seller_id, fund_code, float(sell_shares), float(nav), float(amt)
                )

                if result == 'SUCCESS':
                    logger.info(
                        f"卖出记录 {seller_id}: 基金 {fund_code} 在 {sell_time} "
                        f"卖出份额 {sell_shares} × 净值 {nav} = 金额 {amt}"
                    )
                    success_count += 1
                elif result in ('NO_POSITION', 'OVERSELL'):
                    # 无持仓或超卖，已标记 FAILED，不扣减持仓
                    logger.warning(
                        f"卖出记录 {seller_id}: 基金 {fund_code} 处理结果 {result}，已标记 FAILED"
                    )
                    fail_count += 1
                else:
                    # 'ERROR' - 异常，保持 PENDING，下次重试
                    logger.error(f"卖出记录 {seller_id}: 原子处理异常，保持 PENDING 等待重试")
                    fail_count += 1

            except Exception as e:
                logger.error(f"处理卖出记录 {seller_id} 时发生异常: {e}")
                fail_count += 1

        logger.info(
            f"计算卖出金额任务完成: 成功 {success_count} 条, 失败 {fail_count} 条, "
            f"跳过 {skip_count} 条"
        )

    except Exception as e:
        logger.error(f"计算基金卖出金额任务异常: {e}", extra={
            'category': 'task',
            'task_name': 'calculate_seller_amount_task'
        })
