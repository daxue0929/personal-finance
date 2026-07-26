#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓分析图跳过非交易日测试（TDD）

验证 filter_trading_days：按交易日集合过滤快照序列，剔除非交易日（周末/节假日）点。
"""
from app.analytics.position_analysis import filter_trading_days


def _row(date, val=100):
    return {'snapshot_date': date, 'current_value': val, 'profit_loss': 0}


def test_keeps_only_trading_days():
    """保留交易日行，剔除非交易日（7-18/7-19 周末）"""
    rows = [_row('2026-07-17'), _row('2026-07-18'), _row('2026-07-19'), _row('2026-07-20')]
    trading = {'2026-07-17', '2026-07-20'}
    result = filter_trading_days(rows, trading)
    assert [r['snapshot_date'] for r in result] == ['2026-07-17', '2026-07-20']


def test_empty_trading_dates_returns_all():
    """空 trading_dates 兜底：原样返回（不误删清空）"""
    rows = [_row('2026-07-17'), _row('2026-07-18')]
    assert filter_trading_days(rows, set()) == rows


def test_preserves_order():
    """顺序不变"""
    rows = [_row('2026-07-13'), _row('2026-07-14'), _row('2026-07-15')]
    trading = {'2026-07-13', '2026-07-14', '2026-07-15'}
    result = filter_trading_days(rows, trading)
    assert [r['snapshot_date'] for r in result] == ['2026-07-13', '2026-07-14', '2026-07-15']


def test_empty_rows():
    """空 rows 返回 []"""
    assert filter_trading_days([], {'2026-07-17'}) == []


def test_all_non_trading_removed():
    """全部非交易日 -> 空"""
    rows = [_row('2026-07-18'), _row('2026-07-19')]
    assert filter_trading_days(rows, {'2026-07-17', '2026-07-20'}) == []
