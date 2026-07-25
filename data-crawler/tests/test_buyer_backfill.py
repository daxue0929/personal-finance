#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
买入补录份额计算纯函数测试（TDD）

验证 compute_buyer_shares：份额 = 金额 / 净值，四舍五入 4 位；nav<=0 返回 None。
"""
from decimal import Decimal

from app.storage.fund_buyer_storage import compute_buyer_shares


def test_normal():
    """正常：1000 / 1.5 = 666.6667"""
    assert compute_buyer_shares(1000, 1.5) == Decimal('666.6667')


def test_exact_division():
    """整除：100 / 1 = 100.0000"""
    assert compute_buyer_shares(100, 1) == Decimal('100.0000')


def test_nav_zero():
    """nav=0 -> None"""
    assert compute_buyer_shares(1000, 0) is None


def test_nav_negative():
    """nav<0 -> None"""
    assert compute_buyer_shares(1000, -1) is None


def test_decimal_inputs():
    """兼容 Decimal 输入"""
    assert compute_buyer_shares(Decimal('1000'), Decimal('1.5')) == Decimal('666.6667')


def test_rounding():
    """四舍五入：1000 / 3 = 333.3333... -> 333.3333"""
    assert compute_buyer_shares(1000, 3) == Decimal('333.3333')
