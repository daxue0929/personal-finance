#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓分析纯计算函数测试（TDD）

测试 app/analytics/position_analysis.py 中的纯计算逻辑，不依赖数据库。
覆盖：区间概览、最大回撤、持仓占比。
输入约定：
- snapshots：单持仓的快照序列，按 snapshot_date 升序，每项含
  snapshot_date/current_value/profit_loss/profit_loss_rate（数值或字符串日期）
- allocation 输入：某日全部持仓快照，每项含 fund_code/fund_name/current_value
"""
import pytest

from app.analytics.position_analysis import (
    calc_max_drawdown,
    calc_position_overview,
    calc_position_allocation,
    calc_portfolio_profit_series,
    calc_portfolio_overview,
)


# ==================== 最大回撤 ====================

def test_max_drawdown_monotonic_up():
    """持续上涨：无回撤，返回 0.0"""
    assert calc_max_drawdown([100, 110, 120, 130]) == 0.0


def test_max_drawdown_single_decline():
    """先涨后跌：回撤 = (peak - trough) / peak"""
    # peak=120, trough=90 -> (120-90)/120 = 25%
    assert calc_max_drawdown([100, 120, 90]) == pytest.approx(25.0)


def test_max_drawdown_multiple_peaks():
    """多次涨跌取最大回撤（同一峰值下取最深谷值）"""
    # peak=150，后续最深谷值=80 -> (150-80)/150 = 46.67%
    values = [100, 150, 90, 120, 130, 80]
    assert calc_max_drawdown(values) == pytest.approx(46.67, abs=0.01)


def test_max_drawdown_pure_decline():
    """持续下跌：回撤 = (首 - 末) / 首"""
    assert calc_max_drawdown([100, 80, 60]) == pytest.approx(40.0)


def test_max_drawdown_empty():
    assert calc_max_drawdown([]) is None


def test_max_drawdown_single_point():
    assert calc_max_drawdown([100]) is None


def test_max_drawdown_two_points_up():
    assert calc_max_drawdown([100, 110]) == 0.0


def test_max_drawdown_two_points_down():
    assert calc_max_drawdown([100, 80]) == pytest.approx(20.0)


def test_max_drawdown_recovers_then_declines():
    """回撤后创新高再回撤，取后续更大的回撤"""
    # peak=200, trough=100 -> 50%
    values = [100, 150, 100, 200, 100]
    assert calc_max_drawdown(values) == pytest.approx(50.0)


# ==================== 区间概览 ====================

def _snap(date, value, pl, rate):
    return {
        'snapshot_date': date,
        'current_value': value,
        'profit_loss': pl,
        'profit_loss_rate': rate,
    }


def test_overview_basic():
    snaps = [
        _snap('2026-07-12', 1000.0, 100.0, 11.11),
        _snap('2026-07-13', 1200.0, 200.0, 20.0),
        _snap('2026-07-14', 900.0, -100.0, -10.0),
    ]
    o = calc_position_overview(snaps)
    assert o['count'] == 3
    assert o['start_date'] == '2026-07-12'
    assert o['end_date'] == '2026-07-14'
    assert o['latest_value'] == 900.0
    assert o['latest_profit_loss'] == -100.0
    assert o['latest_profit_loss_rate'] == -10.0
    assert o['max_value'] == 1200.0
    assert o['min_value'] == 900.0
    # peak=1200, trough=900 -> 25%
    assert o['max_drawdown'] == pytest.approx(25.0)
    # 市值变化 = 末 - 首
    assert o['value_change'] == pytest.approx(-100.0)
    # 盈亏变化 = 末盈亏 - 首盈亏
    assert o['profit_loss_change'] == pytest.approx(-200.0)


def test_overview_empty():
    o = calc_position_overview([])
    assert o['count'] == 0


def test_overview_single_point():
    snaps = [_snap('2026-07-12', 1000.0, 50.0, 5.0)]
    o = calc_position_overview(snaps)
    assert o['count'] == 1
    assert o['max_drawdown'] is None  # 单点无法计算回撤
    assert o['max_value'] == 1000.0
    assert o['min_value'] == 1000.0
    assert o['value_change'] == pytest.approx(0.0)


def test_overview_monotonic_no_drawdown():
    snaps = [
        _snap('2026-07-12', 1000.0, 0.0, 0.0),
        _snap('2026-07-13', 1100.0, 100.0, 10.0),
        _snap('2026-07-14', 1200.0, 200.0, 20.0),
    ]
    o = calc_position_overview(snaps)
    assert o['max_drawdown'] == 0.0


def test_overview_decimal_inputs():
    """兼容 Decimal 输入（来自 ORM）"""
    from decimal import Decimal
    snaps = [
        _snap('2026-07-12', Decimal('1000.00'), Decimal('100.00'), Decimal('11.11')),
        _snap('2026-07-13', Decimal('900.00'), Decimal('-100.00'), Decimal('-10.00')),
    ]
    o = calc_position_overview(snaps)
    assert o['latest_value'] == pytest.approx(900.0)
    assert o['max_drawdown'] == pytest.approx(10.0)  # 1000->900 = 10%


# ==================== 持仓占比（饼图）====================

def test_allocation_basic():
    snaps = [
        {'fund_code': '011613', 'fund_name': '基金A', 'current_value': 5000.0},
        {'fund_code': '020292', 'fund_name': '基金B', 'current_value': 3000.0},
        {'fund_code': '160424', 'fund_name': '基金C', 'current_value': 2000.0},
    ]
    result = calc_position_allocation(snaps)
    assert len(result) == 3
    # 按占比降序
    assert result[0]['fund_code'] == '011613'
    assert result[0]['percent'] == pytest.approx(50.0)
    assert result[1]['percent'] == pytest.approx(30.0)
    assert result[2]['percent'] == pytest.approx(20.0)
    # 占比之和 = 100
    total = sum(r['percent'] for r in result)
    assert total == pytest.approx(100.0)


def test_allocation_empty():
    assert calc_position_allocation([]) == []


def test_allocation_all_zero_value():
    """全部市值为 0：返回各 0%，不除零"""
    snaps = [
        {'fund_code': 'A', 'fund_name': 'A', 'current_value': 0.0},
        {'fund_code': 'B', 'fund_name': 'B', 'current_value': 0.0},
    ]
    result = calc_position_allocation(snaps)
    assert len(result) == 2
    assert all(r['percent'] == 0.0 for r in result)


def test_allocation_single():
    snaps = [{'fund_code': '011613', 'fund_name': '基金A', 'current_value': 1000.0}]
    result = calc_position_allocation(snaps)
    assert len(result) == 1
    assert result[0]['percent'] == pytest.approx(100.0)


def test_allocation_decimal():
    from decimal import Decimal
    snaps = [
        {'fund_code': 'A', 'fund_name': 'A', 'current_value': Decimal('5011.84')},
        {'fund_code': 'B', 'fund_name': 'B', 'current_value': Decimal('1888.91')},
    ]
    result = calc_position_allocation(snaps)
    assert result[0]['fund_code'] == 'A'
    assert result[0]['percent'] == pytest.approx(72.63, abs=0.1)


# ==================== 组合级累计收益序列 ====================
# calc_portfolio_profit_series：将「按日聚合后的快照行」转为每日累计盈亏序列。
# 输入约定：rows 为单持仓序列 OR 组合级聚合行，每项含 snapshot_date/current_value/cost_amount/profit_loss。
#   - 单持仓序列：直接透传，序列化为 {snapshot_date, profit_loss}（升序）。
#   - 组合级聚合行：后端已按 snapshot_date SUM 聚合，本函数仅做映射+排序。
# 输出：[{snapshot_date, profit_loss}]，按日期升序。

def test_portfolio_series_single_position_passthrough():
    """单持仓序列：透传为 (date, profit_loss) 序列，升序"""
    rows = [
        _snap('2026-07-12', 1000.0, 100.0, 11.11),
        _snap('2026-07-13', 1200.0, 200.0, 20.0),
        _snap('2026-07-14', 900.0, -50.0, -5.0),
    ]
    series = calc_portfolio_profit_series(rows)
    assert [p['snapshot_date'] for p in series] == ['2026-07-12', '2026-07-13', '2026-07-14']
    assert [p['profit_loss'] for p in series] == [100.0, 200.0, -50.0]


def test_portfolio_series_aggregated_rows():
    """组合级聚合行（已含 SUM 后的 profit_loss）：映射为序列"""
    rows = [
        {'snapshot_date': '2026-07-12', 'profit_loss': 300.0, 'current_value': 3000.0, 'cost_amount': 2700.0},
        {'snapshot_date': '2026-07-13', 'profit_loss': 500.0, 'current_value': 3200.0, 'cost_amount': 2700.0},
    ]
    series = calc_portfolio_profit_series(rows)
    assert len(series) == 2
    assert series[0] == {'snapshot_date': '2026-07-12', 'profit_loss': 300.0}
    assert series[1] == {'snapshot_date': '2026-07-13', 'profit_loss': 500.0}


def test_portfolio_series_unsorted_input_gets_sorted():
    """输入乱序时按日期升序输出"""
    rows = [
        _snap('2026-07-14', 900.0, -50.0, -5.0),
        _snap('2026-07-12', 1000.0, 100.0, 11.11),
        _snap('2026-07-13', 1200.0, 200.0, 20.0),
    ]
    series = calc_portfolio_profit_series(rows)
    assert [p['snapshot_date'] for p in series] == ['2026-07-12', '2026-07-13', '2026-07-14']


def test_portfolio_series_empty():
    """空输入返回空列表"""
    assert calc_portfolio_profit_series([]) == []


def test_portfolio_series_decimal():
    """兼容 Decimal 输入"""
    from decimal import Decimal
    rows = [
        {'snapshot_date': '2026-07-12', 'profit_loss': Decimal('100.00'), 'current_value': Decimal('1000.00'), 'cost_amount': Decimal('900.00')},
        {'snapshot_date': '2026-07-13', 'profit_loss': Decimal('200.00'), 'current_value': Decimal('1100.00'), 'cost_amount': Decimal('900.00')},
    ]
    series = calc_portfolio_profit_series(rows)
    assert series[0]['profit_loss'] == pytest.approx(100.0)
    assert series[1]['profit_loss'] == pytest.approx(200.0)


# ==================== 组合级概览 ====================
# calc_portfolio_overview：对聚合后的组合序列计算概览（与单持仓概览同口径，
# 但基于聚合行 {snapshot_date, current_value, cost_amount, profit_loss}）。

def test_portfolio_overview_basic():
    rows = [
        {'snapshot_date': '2026-07-12', 'current_value': 3000.0, 'cost_amount': 2700.0, 'profit_loss': 300.0},
        {'snapshot_date': '2026-07-13', 'current_value': 3500.0, 'cost_amount': 2700.0, 'profit_loss': 800.0},
        {'snapshot_date': '2026-07-14', 'current_value': 2500.0, 'cost_amount': 2700.0, 'profit_loss': -200.0},
    ]
    o = calc_portfolio_overview(rows)
    assert o['count'] == 3
    assert o['start_date'] == '2026-07-12'
    assert o['end_date'] == '2026-07-14'
    assert o['latest_value'] == 2500.0
    assert o['latest_profit_loss'] == -200.0
    assert o['max_value'] == 3500.0
    assert o['min_value'] == 2500.0
    # peak=3500, trough=2500 -> 28.57%
    assert o['max_drawdown'] == pytest.approx(28.57, abs=0.01)


def test_portfolio_overview_empty():
    assert calc_portfolio_overview([]) == {'count': 0}


def test_portfolio_overview_single_point():
    rows = [{'snapshot_date': '2026-07-12', 'current_value': 1000.0, 'cost_amount': 900.0, 'profit_loss': 100.0}]
    o = calc_portfolio_overview(rows)
    assert o['count'] == 1
    assert o['max_drawdown'] is None
