#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金卖出流水计算逻辑测试（TDD）

测试两层：
1. app.storage.fund_seller_storage._compute_sell_reduction —— 纯计算（加权成本法扣减 + 已实现盈亏），
   不依赖数据库，覆盖正常/部分/全部卖出/超卖边界与精度。
2. app.analytics.position_analysis —— 组合级累计收益序列与概览（已在 test_position_analysis.py 覆盖，此处不重复）。

加权平均成本法约定（与 fund_seller_storage.process_seller_transaction 一致）：
- cost_price 不变
- new_shares = old_shares - sell_shares
- new_cost_amount = old_cost_amount - sell_shares × cost_price
- realized_profit = (nav - cost_price) × sell_shares
- current_value = new_shares × nav
- profit_loss = current_value - new_cost_amount
- 全部卖出（new_shares==0）时 cost_amount/current_value/profit_loss/profit_loss_rate 强制归零
"""
import pytest

from app.storage.fund_seller_storage import _compute_sell_reduction


# ==================== 正常卖出 ====================

def test_sell_reduction_partial():
    """部分卖出：份额/成本金额按比例减少，成本价不变"""
    r = _compute_sell_reduction(
        old_shares=100.0, cost_price=2.0, old_cost_amount=200.0,
        sell_shares=30.0, nav=2.5
    )
    assert r['ok'] is True
    assert r['new_shares'] == pytest.approx(70.0)
    # new_cost_amount = 200 - 30*2.0 = 140
    assert r['new_cost_amount'] == pytest.approx(140.0)
    # realized_profit = (2.5 - 2.0) * 30 = 15
    assert r['realized_profit'] == pytest.approx(15.0)
    # current_value = 70 * 2.5 = 175
    assert r['current_value'] == pytest.approx(175.0)
    # profit_loss = 175 - 140 = 35
    assert r['profit_loss'] == pytest.approx(35.0)
    # profit_loss_rate = 35/140*100 = 25
    assert r['profit_loss_rate'] == pytest.approx(25.0)


def test_sell_reduction_realized_loss():
    """亏本卖出：realized_profit 为负"""
    r = _compute_sell_reduction(
        old_shares=100.0, cost_price=2.0, old_cost_amount=200.0,
        sell_shares=50.0, nav=1.5
    )
    # realized_profit = (1.5 - 2.0) * 50 = -25
    assert r['realized_profit'] == pytest.approx(-25.0)
    assert r['ok'] is True


def test_sell_reduction_full():
    """全部卖出：new_shares=0，盈亏字段强制归零，避免 -100% 残留"""
    r = _compute_sell_reduction(
        old_shares=100.0, cost_price=2.0, old_cost_amount=200.0,
        sell_shares=100.0, nav=2.5
    )
    assert r['ok'] is True
    assert r['new_shares'] == 0
    assert r['new_cost_amount'] == 0
    assert r['current_value'] == 0
    assert r['profit_loss'] == 0
    assert r['profit_loss_rate'] == 0
    # realized_profit = (2.5 - 2.0) * 100 = 50
    assert r['realized_profit'] == pytest.approx(50.0)


def test_sell_reduction_decimal_inputs():
    """兼容 Decimal 输入（来自 ORM）"""
    from decimal import Decimal
    r = _compute_sell_reduction(
        old_shares=Decimal('142.4300'), cost_price=Decimal('3.5105'),
        old_cost_amount=Decimal('500.00'),
        sell_shares=Decimal('50.0000'), nav=Decimal('3.3617')
    )
    assert r['ok'] is True
    assert r['new_shares'] == pytest.approx(92.43)
    # realized_profit = (3.3617 - 3.5105) * 50 = -7.44
    assert r['realized_profit'] == pytest.approx(-7.44, abs=0.01)


# ==================== 超卖边界 ====================

def test_sell_reduction_oversell():
    """卖出份额 > 持仓份额：返回 ok=False（超卖）"""
    r = _compute_sell_reduction(
        old_shares=100.0, cost_price=2.0, old_cost_amount=200.0,
        sell_shares=150.0, nav=2.5
    )
    assert r['ok'] is False


def test_sell_reduction_exact_equal():
    """卖出份额 == 持仓份额：等于全部卖出，ok=True，归零"""
    r = _compute_sell_reduction(
        old_shares=100.0, cost_price=2.0, old_cost_amount=200.0,
        sell_shares=100.0, nav=2.0
    )
    assert r['ok'] is True
    assert r['new_shares'] == 0
    # realized_profit = (2.0 - 2.0) * 100 = 0
    assert r['realized_profit'] == 0


# ==================== 精度 ====================

def test_sell_reduction_rounding():
    """金额字段 round 到 2 位，份额不额外 round（由调用方量化）"""
    r = _compute_sell_reduction(
        old_shares=100.0, cost_price=2.0, old_cost_amount=200.0,
        sell_shares=33.0, nav=2.3333
    )
    # current_value = 67 * 2.3333 = 156.3311 -> round 156.33
    assert r['current_value'] == pytest.approx(156.33)
    # realized_profit = (2.3333 - 2.0) * 33 = 11.0 -> 11.0
    assert r['realized_profit'] == pytest.approx(11.0)
