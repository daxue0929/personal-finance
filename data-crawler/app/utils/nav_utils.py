#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金净值获取公共逻辑

供 calculate_buyer_shares_task（买入份额计算）与 calculate_seller_amount_task
（卖出金额计算）共用，保证两侧净值查找逻辑一致，避免逐字复制导致后续修改遗漏。

净值匹配语义：必须用与「交易日期」完全匹配的净值日期来计算份额/金额。
  1. 先查 fund_info：net_value_date 须等于交易日期且 net_asset_value 非空
  2. 回退查 fund_nav_history：当日 unit_nav
均无法获取则返回 None，调用方据此跳过（保持 PENDING，下次重试）。
"""


def get_nav_value_by_date(fund_info_storage, nav_history_storage,
                          fund_code: str, nav_date: str) -> float:
    """
    获取基金在指定日期的净值（精确日期匹配）

    Args:
        fund_info_storage: 基金信息存储实例
        nav_history_storage: 净值历史存储实例
        fund_code: 基金代码
        nav_date: 净值日期（YYYY-MM-DD）

    Returns:
        净值值，如果无法获取则返回 None
    """
    # 1. 先尝试从基金信息表获取（日期必须完全匹配）
    fund_info = fund_info_storage.get_fund_by_code(fund_code)
    if fund_info and fund_info.net_value_date:
        fund_nav_date = str(fund_info.net_value_date)
        if fund_nav_date == nav_date and fund_info.net_asset_value:
            return float(fund_info.net_asset_value)

    # 2. 从净值历史表获取（日期必须完全匹配）
    nav_record = nav_history_storage.get_nav_by_fund_date(fund_code, nav_date)
    if nav_record and nav_record.get('unit_nav'):
        return float(nav_record['unit_nav'])

    return None
