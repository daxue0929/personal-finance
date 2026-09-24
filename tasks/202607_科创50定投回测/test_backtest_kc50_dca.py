#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测引擎 单元测试 (TDD: 先于实现)。

用合成价格序列验证 run_backtest 的核心逻辑, 不依赖数据库。
关键验证点:
  - 恒定市空仓不触发止盈
  - 10% 档触发卖 30%、平均成本不变
  - 20% 档清仓(卖出 100%), 持仓归零
  - 重装规则: on_clear 仅 20% 清仓后重装; on_dip 跌破 10% 即重装
  - XIRR 基本正确性

运行: conda run -n personal-finance python -m unittest tasks.test_backtest_kc50_dca
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca import run_backtest, _xirr, TIERS, DAILY_INVEST


def _dates(n, start=date(2020, 1, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def make_prices(tail, n_flat=100, flat_price=100.0):
    """前 n_flat 天恒定 flat_price(累积底仓, 平均成本≈flat_price), 后接 tail 价格序列。"""
    full = [flat_price] * n_flat + list(tail)
    return list(zip(_dates(len(full)), full))


def approx(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def tiers_of(events):
    return [e['tier'] for e in events]


class TestConstants(unittest.TestCase):
    def test_daily_invest_and_tiers(self):
        self.assertTrue(approx(DAILY_INVEST, 300.0))
        self.assertEqual(TIERS, [(0.10, 0.30, '10%'), (0.15, 0.30, '15%'), (0.20, 1.00, '20%')])


class TestXIRR(unittest.TestCase):
    def test_one_year_ten_percent(self):
        d0 = date(2020, 1, 1)
        cf = [(d0, -100.0), (d0 + timedelta(days=365), 110.0)]
        self.assertTrue(approx(_xirr(cf), 0.10, 1e-4))

    def test_empty_returns_zero(self):
        self.assertEqual(_xirr([]), 0.0)


class TestFlatMarket(unittest.TestCase):
    def test_no_trigger(self):
        prices = make_prices([], n_flat=50)
        events, s = run_backtest(prices)
        self.assertEqual(events, [])
        self.assertEqual(s['n_events'], 0)
        # 恒定 100, 50 天, 每天 300 -> 150 份, 成本 15000, 收益率 0
        self.assertTrue(approx(s['final_shares'], 50 * DAILY_INVEST / 100.0))
        self.assertTrue(approx(s['final_cost'], 50 * DAILY_INVEST))
        self.assertTrue(approx(s['total_return'], 0.0))


class TestTenPctTier(unittest.TestCase):
    def test_fires_once_sells_30pct_avg_cost_unchanged(self):
        # 100 天 @100 累积, 第 101 天 @112 -> 收益率≈11.88%(>=10%, <15%), 仅 10% 档触发
        prices = make_prices([112.0], n_flat=100)
        events, s = run_backtest(prices)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e['tier'], '10%')
        self.assertTrue(approx(e['shares_sold'], e['shares_before'] * 0.30))
        self.assertTrue(approx(e['shares_after'], e['shares_before'] * 0.70))
        # 平均成本法: 比例结转, 卖出后平均成本不变
        self.assertTrue(approx(e['cost_before'] / e['shares_before'],
                               e['cost_after'] / e['shares_after']))
        self.assertTrue(approx(e['sell_proceeds'], e['shares_sold'] * e['price']))


class TestTwentyPctClear(unittest.TestCase):
    def test_clears_position_on_20pct(self):
        # 100 天 @100, 第 101 天 @122 -> 收益率≈21.78%(>=20%), 当日 10/15/20% 依次触发,
        # 20% 档卖出 100%, 该事件后持仓归零
        prices = make_prices([122.0], n_flat=100)
        events, s = run_backtest(prices)
        self.assertTrue(len(events) >= 1)
        last = events[-1]
        self.assertEqual(last['tier'], '20%')
        self.assertTrue(approx(last['shares_sold'], last['shares_before']))   # 卖全部
        self.assertTrue(approx(last['shares_after'], 0.0))                    # 持仓归零


class TestRearmOnClear(unittest.TestCase):
    """用户选择的重装规则: 仅 20% 清仓后重装; 跌破 10% 不重装。"""

    PATH = make_prices(
        [112.0]            # A: 触发 10%(disarm 10%)
        + [100.0] * 50     # B: 回落到 ~0% 收益, on_clear 不重装; on_dip 重装
        + [112.0, 112.0]   # C: 再回 10% 区间; on_clear 不触发, on_dip 触发 10%
        + [125.0]          # D: 冲 20%+ -> 15%、20% 触发, 20% 清仓重装
        + [100.0] * 100    # E: 重新累积底仓
        + [112.0],         # F: 再次触发 10%(证明 20% 清仓后已重装)
        n_flat=100,
    )

    def test_on_clear_no_dip_rearm_but_rearms_after_clear(self):
        events, s = run_backtest(self.PATH, rearm_mode='on_clear')
        seq = tiers_of(events)
        # A:10% -> (B,C 无事件, 10% 未重装) -> D:15%,20%(清仓重装) -> F:10%(重装后再次触发)
        self.assertEqual(seq, ['10%', '15%', '20%', '10%'])
        # 20% 事件清仓
        twenty = [e for e in events if e['tier'] == '20%'][0]
        self.assertTrue(approx(twenty['shares_after'], 0.0))


class TestRearmOnDip(unittest.TestCase):
    """对照: on_dip 跌破 10% 即重装, 10% 档会在多轮小级别上涨中反复触发。"""

    def test_on_dip_rearms_on_dip(self):
        path = TestRearmOnClear.PATH
        events, s = run_backtest(path, rearm_mode='on_dip')
        seq = tiers_of(events)
        # A:10% -> B 回落重装 -> C:10%(重装后再触发) -> D:15%,20% -> F:10%
        self.assertEqual(seq, ['10%', '10%', '15%', '20%', '10%'])


class TestSummarySanity(unittest.TestCase):
    def test_total_profit_equals_assets_minus_invested(self):
        prices = make_prices([112.0, 108.0, 115.0], n_flat=30)
        events, s = run_backtest(prices)
        assets = s['final_value'] + s['total_sell_proceeds']   # 回款闲置作现金
        self.assertTrue(approx(s['total_profit'], assets - s['total_invested']))
        self.assertEqual(s['n_events'], len(events))
        self.assertTrue(s['years'] > 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
