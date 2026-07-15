#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金定投计划规则匹配测试（TDD）

测试 app.utils.dip_utils.should_dip_today -- 纯函数，判断给定日期是否命中定投规则，
不依赖数据库、不依赖"当前时间"（today 由参数传入，便于测试任意日期）。

定投频率约定：
- daily：每个自然日都命中（dip_day 忽略）
- weekly：dip_day 为 1-7（1=周一 … 7=周日），today 的 weekday()+1 == dip_day 命中
- monthly：dip_day 为 1-28，today.day == dip_day 命中

背景：净值更新任务每30分钟跑，更新成功后检查所有启用定投计划，命中当天且当天有净值
（仅交易日）才插一条当天 PENDING 买入流水，由 calculate_buyer_shares_task 计算份额。
幂等由 fund_buyer.uk_fund_code_time 唯一键保证（同基金同天只一条）。
"""
from datetime import date

import pytest

from app.utils.dip_utils import should_dip_today


# ==================== daily 每日 ====================

def test_dip_daily_hits_every_day():
    """daily：每天都命中（dip_day 为空或任意值都忽略）"""
    for d in [date(2026, 7, 13), date(2026, 7, 14), date(2026, 7, 15)]:
        assert should_dip_today('daily', None, d) is True
        assert should_dip_today('daily', '', d) is True


def test_dip_daily_ignores_dip_day():
    """daily：即使传了 dip_day 也忽略，仍命中"""
    assert should_dip_today('daily', '3', date(2026, 7, 13)) is True


# ==================== weekly 每周 ====================

def test_dip_weekly_monday():
    """weekly：dip_day=1（周一），2026-07-13 是周一命中"""
    # 2026-07-13 是星期一
    assert date(2026, 7, 13).weekday() == 0  # Monday=0
    assert should_dip_today('weekly', '1', date(2026, 7, 13)) is True


def test_dip_weekly_misses_other_day():
    """weekly：dip_day=1（周一），周二不命中"""
    assert should_dip_today('weekly', '1', date(2026, 7, 14)) is False  # 周二


def test_dip_weekly_sunday():
    """weekly：dip_day=7（周日），2026-07-19 是周日命中"""
    assert date(2026, 7, 19).weekday() == 6  # Sunday=6
    assert should_dip_today('weekly', '7', date(2026, 7, 19)) is True


def test_dip_weekly_all_days():
    """weekly：遍历一周，每天只命中自己对应的 dip_day"""
    # 2026-07-13(周一) 到 2026-07-19(周日)
    week = [date(2026, 7, 13) + __import__('datetime').timedelta(days=i) for i in range(7)]
    for i, d in enumerate(week):
        # i=0 周一 -> dip_day '1' 命中，其它不命中
        assert should_dip_today('weekly', str(i + 1), d) is True
        for j in range(1, 8):
            if j != i + 1:
                assert should_dip_today('weekly', str(j), d) is False


# ==================== monthly 每月 ====================

def test_dip_monthly_hits():
    """monthly：dip_day=10，每月10号命中"""
    assert should_dip_today('monthly', '10', date(2026, 7, 10)) is True
    assert should_dip_today('monthly', '10', date(2026, 8, 10)) is True


def test_dip_monthly_misses():
    """monthly：dip_day=10，非10号不命中"""
    assert should_dip_today('monthly', '10', date(2026, 7, 11)) is False
    assert should_dip_today('monthly', '10', date(2026, 7, 9)) is False


def test_dip_monthly_last_day():
    """monthly：dip_day=28，2月28号命中（避免31号在某些月份不存在）"""
    assert should_dip_today('monthly', '28', date(2026, 2, 28)) is True


def test_dip_monthly_rejects_29_to_31():
    """monthly：dip_day 限 1-28，29/30/31 应被拒（避免某些月份无这些号导致投期不规律）"""
    assert should_dip_today('monthly', '29', date(2026, 3, 29)) is False
    assert should_dip_today('monthly', '30', date(2026, 3, 30)) is False
    assert should_dip_today('monthly', '31', date(2026, 3, 31)) is False


# ==================== 边界与异常 ====================

def test_dip_disabled_when_not_enabled():
    """enable_dip='0' 时不命中（should_dip_today 不处理 enable，由调用方过滤，
    这里测空 frequency 兜底返回 False）"""
    assert should_dip_today('', None, date(2026, 7, 13)) is False
    assert should_dip_today(None, None, date(2026, 7, 13)) is False


def test_dip_unknown_frequency():
    """未知频率返回 False（保守不触发）"""
    assert should_dip_today('quarterly', '1', date(2026, 7, 13)) is False


def test_dip_weekly_invalid_dip_day():
    """weekly 的 dip_day 非法（非数字）返回 False，不抛异常"""
    assert should_dip_today('weekly', 'abc', date(2026, 7, 13)) is False
    assert should_dip_today('weekly', None, date(2026, 7, 13)) is False


def test_dip_monthly_invalid_dip_day():
    """monthly 的 dip_day 非法返回 False，不抛异常"""
    assert should_dip_today('monthly', 'abc', date(2026, 7, 10)) is False
    assert should_dip_today('monthly', None, date(2026, 7, 10)) is False
