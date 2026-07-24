#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓成本价↔指数对应（规则 B：逐日比例）纯函数测试（TDD）

验证 compute_cost_index_series：
- 每日 ratio(t) = 当日指数收盘 / 当日快照基金净值(current_price)
- cost_in_index(t) = cost_price(t) × ratio(t)
- 某日无指数收盘 -> 该点 index_close=None、cost_in_index=None
- has_index = 是否提供了指数日线
"""
import pytest
from decimal import Decimal

from app.analytics.position_analysis import compute_cost_index_series


def _snap(date, cost, cur):
    return {'snapshot_date': date, 'cost_price': cost, 'current_price': cur}


def _idx(date, close):
    return {'trade_date': date, 'close_price': close}


def test_normal_per_date_ratio():
    """正常：每日 ratio=当日指数/当日净值，cost_in_index=cost_price×ratio"""
    snaps = [_snap('2026-07-01', 1.00, 1.00), _snap('2026-07-02', 1.20, 1.50)]
    idx = [_idx('2026-07-01', 3000), _idx('2026-07-02', 3000)]
    r = compute_cost_index_series(snaps, idx)
    assert r['has_index'] is True
    assert len(r['points']) == 2
    p0, p1 = r['points']
    # 7.01: 1.00 × 3000/1.00 = 3000
    assert p0['cost_price'] == pytest.approx(1.00)
    assert p0['index_close'] == pytest.approx(3000.0)
    assert p0['cost_in_index'] == pytest.approx(3000.0)
    # 7.02: 1.20 × 3000/1.50 = 2400
    assert p1['cost_price'] == pytest.approx(1.20)
    assert p1['cost_in_index'] == pytest.approx(2400.0)


def test_index_close_missing_for_some_dates():
    """指数某日缺失 -> 该点 index_close=None、cost_in_index=None（不能用别的日 ratio）"""
    snaps = [_snap('2026-07-01', 1.00, 1.00), _snap('2026-07-02', 1.20, 1.50)]
    idx = [_idx('2026-07-02', 3000)]  # 7.01 缺失
    r = compute_cost_index_series(snaps, idx)
    assert r['has_index'] is True
    assert r['points'][0]['index_close'] is None
    assert r['points'][0]['cost_in_index'] is None  # 7.01 无指数，无法算
    assert r['points'][1]['cost_in_index'] == pytest.approx(2400.0)


def test_no_index_history():
    """无指数日线 -> has_index=False，各点 cost_in_index=None（但 cost_price 仍返回）"""
    snaps = [_snap('2026-07-01', 1.00, 1.00)]
    r = compute_cost_index_series(snaps, [])
    assert r['has_index'] is False
    assert r['points'][0]['cost_in_index'] is None
    assert r['points'][0]['index_close'] is None
    assert r['points'][0]['cost_price'] == pytest.approx(1.00)


def test_no_snapshots():
    """无快照 -> points 空、has_index False"""
    r = compute_cost_index_series([], [_idx('2026-07-01', 3000)])
    assert r['points'] == []
    assert r['has_index'] is False


def test_single_point():
    """单点"""
    snaps = [_snap('2026-07-01', 1.00, 1.00)]
    idx = [_idx('2026-07-01', 3000)]
    r = compute_cost_index_series(snaps, idx)
    assert r['has_index'] is True
    # 1.00 × 3000/1.00 = 3000
    assert r['points'][0]['cost_in_index'] == pytest.approx(3000.0)


def test_decimal_inputs():
    """兼容 Decimal 输入（来自 ORM）"""
    snaps = [_snap('2026-07-01', Decimal('1.00'), Decimal('1.00')),
             _snap('2026-07-02', Decimal('1.20'), Decimal('1.50'))]
    idx = [_idx('2026-07-02', Decimal('3000'))]
    r = compute_cost_index_series(snaps, idx)
    assert r['points'][1]['cost_in_index'] == pytest.approx(2400.0)
