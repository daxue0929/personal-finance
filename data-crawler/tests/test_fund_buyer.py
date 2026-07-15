#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金买入流水持仓累加计算逻辑测试（TDD）

测试 app.storage.fund_buyer_storage._compute_buyer_accumulation -- 纯计算（加权成本法累加），
不依赖数据库，覆盖正常累加/加权成本价重算/首笔买入/同日多笔合并/Decimal 兼容与精度。

与卖出侧 _compute_sell_reduction（见 test_fund_seller.py）对称，加权平均成本法约定：
- weighted_cost_price = (old_cost_amount + buy_amt) / new_total_shares
- new_total_shares = old_shares + buy_shares
- new_cost_amount = old_cost_amount + buy_amt
- current_value = new_total_shares × current_price
- profit_loss = current_value - new_cost_amount
- profit_loss_rate = profit_loss / new_cost_amount × 100

背景：calculate_buyer_shares_task 原先用 position.buy_date 做幂等水位（流水买入日期 <= 持仓买入日期
则跳过），导致补录历史/同日买入被错误跳过、份额漏加。改造为原子事务后，累加计算抽成此纯函数，
幂等改由 PENDING 状态机 + 原子事务保证，不再依赖日期水位。
"""
import pytest
from decimal import Decimal

from app.storage.fund_buyer_storage import _compute_buyer_accumulation


# ==================== 正常累加 ====================

def test_buy_accumulation_normal():
    """正常累加：份额相加，加权成本价重算"""
    r = _compute_buyer_accumulation(
        old_shares=100.0, old_cost_amount=200.0,
        buy_shares=50.0, buy_amt=150.0, current_price=3.0
    )
    assert r['ok'] is True
    # new_total_shares = 100 + 50 = 150
    assert r['new_total_shares'] == pytest.approx(150.0)
    # new_cost_amount = 200 + 150 = 350
    assert r['new_cost_amount'] == pytest.approx(350.0)
    # weighted_cost_price = 350 / 150 = 2.3333...
    assert r['weighted_cost_price'] == pytest.approx(350.0 / 150.0)
    # current_value = 150 * 3.0 = 450
    assert r['current_value'] == pytest.approx(450.0)
    # profit_loss = 450 - 350 = 100
    assert r['profit_loss'] == pytest.approx(100.0)
    # profit_loss_rate = 100 / 350 * 100 = 28.5714... -> round 28.57（与卖出侧一致保留2位）
    assert r['profit_loss_rate'] == pytest.approx(28.57)


def test_buy_accumulation_weighted_cost_price():
    """加权成本价：低价加仓拉低均价"""
    # 原持仓 100 份 @ 2.0（成本 200），现以 1.0 净值买 100 份（金额 100）
    r = _compute_buyer_accumulation(
        old_shares=100.0, old_cost_amount=200.0,
        buy_shares=100.0, buy_amt=100.0, current_price=1.5
    )
    assert r['ok'] is True
    # 加权成本价 = (200 + 100) / 200 = 1.5（被低价加仓拉低到 1.5）
    assert r['weighted_cost_price'] == pytest.approx(1.5)
    assert r['new_total_shares'] == pytest.approx(200.0)
    assert r['new_cost_amount'] == pytest.approx(300.0)


def test_buy_accumulation_first_buy():
    """首笔买入（old_shares=0）：成本价 = 买入净值，无加权"""
    r = _compute_buyer_accumulation(
        old_shares=0.0, old_cost_amount=0.0,
        buy_shares=100.0, buy_amt=200.0, current_price=2.0
    )
    assert r['ok'] is True
    assert r['new_total_shares'] == pytest.approx(100.0)
    assert r['new_cost_amount'] == pytest.approx(200.0)
    # weighted_cost_price = 200 / 100 = 2.0
    assert r['weighted_cost_price'] == pytest.approx(2.0)
    # current_value = 100 * 2.0 = 200, profit_loss = 0
    assert r['current_value'] == pytest.approx(200.0)
    assert r['profit_loss'] == pytest.approx(0.0)
    assert r['profit_loss_rate'] == pytest.approx(0.0)


def test_buy_accumulation_same_day_multiple_merges():
    """同日多笔买入合并：等价于一次性累加总份额与总金额"""
    # 同日两笔：50份@100元 + 50份@200元，合并成 100份 300元
    r = _compute_buyer_accumulation(
        old_shares=100.0, old_cost_amount=200.0,
        buy_shares=100.0, buy_amt=300.0, current_price=2.5
    )
    assert r['ok'] is True
    assert r['new_total_shares'] == pytest.approx(200.0)
    assert r['new_cost_amount'] == pytest.approx(500.0)
    # 加权成本价 = 500 / 200 = 2.5
    assert r['weighted_cost_price'] == pytest.approx(2.5)


# ==================== Decimal 兼容 ====================

def test_buy_accumulation_decimal_inputs():
    """兼容 Decimal 输入（来自 ORM）"""
    r = _compute_buyer_accumulation(
        old_shares=Decimal('142.4300'), old_cost_amount=Decimal('500.00'),
        buy_shares=Decimal('50.0000'), buy_amt=Decimal('175.50'),
        current_price=Decimal('3.3617')
    )
    assert r['ok'] is True
    # new_total_shares = 142.43 + 50 = 192.43
    assert r['new_total_shares'] == pytest.approx(192.43)
    # new_cost_amount = 500 + 175.50 = 675.50
    assert r['new_cost_amount'] == pytest.approx(675.50)
    # weighted_cost_price = 675.50 / 192.43 ≈ 3.5105
    assert r['weighted_cost_price'] == pytest.approx(675.50 / 192.43, abs=0.0001)


# ==================== 精度 ====================

def test_buy_accumulation_rounding():
    """金额字段 round 到 2 位，加权成本价保留足够精度（由调用方量化）"""
    r = _compute_buyer_accumulation(
        old_shares=100.0, old_cost_amount=200.0,
        buy_shares=33.0, buy_amt=76.9889, current_price=2.3333
    )
    assert r['ok'] is True
    # new_cost_amount = 200 + 76.9889 = 276.9889 -> round 276.99
    assert r['new_cost_amount'] == pytest.approx(276.99)
    # current_value = 133 * 2.3333 = 310.3289 -> round 310.33
    assert r['current_value'] == pytest.approx(310.33)
    # profit_loss = 310.33 - 276.99 = 33.34
    assert r['profit_loss'] == pytest.approx(310.33 - 276.99, abs=0.01)


def test_buy_accumulation_zero_cost_amount_rate():
    """cost_amount 为 0 时 profit_loss_rate 归零，避免除零"""
    r = _compute_buyer_accumulation(
        old_shares=0.0, old_cost_amount=0.0,
        buy_shares=0.0, buy_amt=0.0, current_price=2.0
    )
    assert r['ok'] is True
    assert r['new_total_shares'] == 0
    assert r['new_cost_amount'] == 0
    assert r['profit_loss_rate'] == 0
