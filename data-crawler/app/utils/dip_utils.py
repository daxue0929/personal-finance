#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金定投规则匹配公共逻辑

供 update_fund_net_values_task（净值更新任务）在净值更新成功后检查定投计划是否命中当天。
纯函数 should_dip_today 不依赖数据库与"当前时间"，便于单元测试。

定投频率约定：
- daily：每个自然日都命中（dip_day 忽略）
- weekly：dip_day 为 1-7（1=周一 … 7=周日），today 的 weekday()+1 == dip_day 命中
- monthly：dip_day 为 1-28，today.day == dip_day 命中
"""

from datetime import date


def should_dip_today(dip_frequency, dip_day, today: date) -> bool:
    """
    判断给定日期是否命中定投规则

    Args:
        dip_frequency: 定投频率 daily/weekly/monthly
        dip_day: 定投日。daily 忽略；weekly 为 '1'-'7'；monthly 为 '1'-'28'
        today: 要判断的日期（date 对象）

    Returns:
        True 表示当天命中定投规则；False 表示不命中或参数非法（保守不触发）
    """
    if not dip_frequency:
        return False

    freq = str(dip_frequency).strip().lower()

    if freq == 'daily':
        # 每个自然日都命中，dip_day 忽略
        return True

    if freq == 'weekly':
        # dip_day 1-7 对应周一到周日；date.weekday() 周一=0 … 周日=6
        if not dip_day:
            return False
        try:
            target = int(dip_day)
        except (TypeError, ValueError):
            return False
        if not 1 <= target <= 7:
            return False
        return today.weekday() + 1 == target

    if freq == 'monthly':
        # dip_day 1-28 对应每月几号（限 28 以内避免某些月份无 29/30/31 号）
        if not dip_day:
            return False
        try:
            target = int(dip_day)
        except (TypeError, ValueError):
            return False
        if not 1 <= target <= 28:
            return False
        return today.day == target

    # 未知频率，保守不触发
    return False
