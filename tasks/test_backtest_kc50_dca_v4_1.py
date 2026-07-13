#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测 V4 引擎 单元测试 (TDD: 先于实现)。

V4 = V3 去掉 10% 档: 首档 15%, 共 8 档(15%~50%), 其余规则同 V3:
  - 卖比 = 2×档位(15%卖30%、20%卖40%…50%卖100%清仓)
  - 重装阈值 L−2.5%
  - DCA 再触发推广到 15%~45% 全部 7 档, 按档位独立追踪

动机: V3 报告发现「10% 档过早过频削薄底仓(17 次)」是 V3 弱于 V2 的主因之一,
V4 去掉 10% 档以验证能否让收益回升。

关键验证点:
  - 无 10% 档: 10%~15% 区间不触发(@112 不卖)
  - 15% 为首档, 卖 30%
  - 20% 档卖 40%(递增卖比)
  - 45% 档留底仓(未清仓), 50% 档清仓
  - 15% 档 DCA 再触发
  - 重装 15% 跌破 12.5%
  - XIRR、汇总恒等式

运行: conda run -n personal-finance python -m unittest tasks.test_backtest_kc50_dca_v4
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca_v4_1 import (
    run_backtest_v4, DAILY_INVEST, TIER_STEP, FIRST_TIER, REARM_OFFSET,
    TIER_SELL_FRAC, TIERS,
)


def _dates(n, start=date(2020, 1, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def make_prices(tail, n_flat=100, flat_price=100.0):
    """前 n_flat 天恒定 flat_price(累积底仓, 平均成本≈flat_price), 后接 tail。"""
    full = [flat_price] * n_flat + list(tail)
    return list(zip(_dates(len(full)), full))


def approx(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def tiers_of(events):
    return [e['tier'] for e in events]


def triggers_of(events):
    return [e['trigger'] for e in events]


class TestConstants(unittest.TestCase):
    def test_params(self):
        self.assertTrue(approx(DAILY_INVEST, 300.0))
        self.assertTrue(approx(FIRST_TIER, 0.15))      # 首档 15%(去掉 10%)
        self.assertTrue(approx(TIER_STEP, 0.05))
        self.assertTrue(approx(REARM_OFFSET, 0.025))
        # 无 10% 档: TIERS 从 15% 起
        self.assertNotIn(0.10, TIERS)
        self.assertEqual(TIERS[0], 0.15)
        self.assertEqual(TIERS[-1], 0.50)
        self.assertEqual(len(TIERS), 8)                 # 15%~50% 共 8 档
        # 卖比 = 2×档位
        self.assertTrue(approx(TIER_SELL_FRAC[0.15], 0.30))
        self.assertTrue(approx(TIER_SELL_FRAC[0.20], 0.40))
        self.assertTrue(approx(TIER_SELL_FRAC[0.25], 0.50))
        self.assertTrue(approx(TIER_SELL_FRAC[0.30], 0.60))
        self.assertTrue(approx(TIER_SELL_FRAC[0.35], 0.70))
        self.assertTrue(approx(TIER_SELL_FRAC[0.40], 0.80))
        self.assertTrue(approx(TIER_SELL_FRAC[0.45], 0.90))
        self.assertTrue(approx(TIER_SELL_FRAC[0.50], 1.00))


class TestNoTenPctTier(unittest.TestCase):
    def test_no_trigger_below_15pct(self):
        # @112 -> 收益率≈11.5%(<15%), V4 无 10% 档, 不触发任何止盈
        prices = make_prices([112.0], n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertEqual(events, [])
        self.assertEqual(s['n_events'], 0)


class TestFlatMarket(unittest.TestCase):
    def test_no_trigger(self):
        prices = make_prices([], n_flat=50)
        events, s = run_backtest_v4(prices)
        self.assertEqual(events, [])
        self.assertEqual(s['n_events'], 0)
        self.assertTrue(approx(s['total_return'], 0.0))


class TestSellFraction15pct(unittest.TestCase):
    def test_fires_once_sells_30pct(self):
        # @118 -> 收益率≈17.5%(>=15%, <20%), 仅 15% 档, 卖 30%
        prices = make_prices([118.0], n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e['tier'], '15%')
        self.assertEqual(e['trigger'], 'normal')
        self.assertTrue(approx(e['shares_sold'], e['shares_before'] * 0.30))
        self.assertTrue(approx(e['shares_after'], e['shares_before'] * 0.70))
        # 平均成本法: 比例结转, 卖出后平均成本不变
        self.assertTrue(approx(e['cost_before'] / e['shares_before'],
                               e['cost_after'] / e['shares_after']))
        self.assertTrue(approx(e['sell_proceeds'], e['shares_sold'] * e['price']))


class TestSellFraction20pct(unittest.TestCase):
    def test_20pct_sells_40pct(self):
        # @125 -> 收益率≈24.5%(>=20%), 触发 15%(卖30%) + 20%(卖40%)
        prices = make_prices([125.0], n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertEqual(tiers_of(events), ['15%', '20%'])
        e20 = events[1]
        self.assertTrue(approx(e20['shares_sold'], e20['shares_before'] * 0.40))
        self.assertTrue(approx(e20['shares_after'], e20['shares_before'] * 0.60))


class TestClearAtFiftyPct(unittest.TestCase):
    def test_clears_position_at_50pct(self):
        # @160 -> 收益率≈59%(>=50%), 触发 15%~50%, 50% 档卖 100% 清仓
        prices = make_prices([160.0], n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertTrue(len(events) >= 1)
        last = events[-1]
        self.assertEqual(last['tier'], '50%')
        self.assertTrue(approx(last['shares_sold'], last['shares_before']))  # 卖全部
        self.assertTrue(approx(last['shares_after'], 0.0))                  # 清仓


class TestNeverEmptyAtFortyFive(unittest.TestCase):
    def test_keeps_position_below_50pct(self):
        # @146 -> 收益率≈45.4%(>=45%, <50%), 触发 15%~45%, 50% 不触发, 仍留底仓
        prices = make_prices([146.0], n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertNotIn('50%', tiers_of(events))
        self.assertIn('45%', tiers_of(events))
        self.assertTrue(s['final_shares'] > 0, f"45% 档未清仓应留底仓: {s['final_shares']}")


class TestDcaRetrigger15pct(unittest.TestCase):
    def test_dca_retrigger_at_15pct_band(self):
        # @117(触发15%, 卖30%) -> @120×18 在[15%,20%)震荡, 15% DCA 再触发
        # (V4 无 10% 档, @117 仅触发 15%; 实际收益率因定投稀释约 16.5%, 满足>=15%)
        prices = make_prices([117.0] + [120.0] * 18, n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertEqual(events[0]['tier'], '15%')
        self.assertEqual(events[0]['trigger'], 'normal')
        dca_15 = [e for e in events if e['tier'] == '15%' and e['trigger'] == 'dca_retrigger']
        self.assertTrue(len(dca_15) >= 1, f"应至少 1 次 15% DCA 再触发: {tiers_of(events)}")
        e15_first = events[0]
        self.assertTrue(dca_15[0]['dca_at_trigger'] >= e15_first['sell_proceeds'] / 2.0 - 1e-6)


class TestRearmBelowLMinus2_5(unittest.TestCase):
    def test_rearm_15pct_below_12_5pct(self):
        # @118(触发15%) -> @112(11.5%, 跌破12.5%重装15%) -> @118(再触发15%, normal)
        prices = make_prices([118.0, 112.0, 118.0], n_flat=100)
        events, s = run_backtest_v4(prices)
        self.assertEqual(tiers_of(events), ['15%', '15%'])
        self.assertEqual(triggers_of(events), ['normal', 'normal'])


class TestSummarySanity(unittest.TestCase):
    def test_total_profit_identity(self):
        prices = make_prices([118.0, 108.0, 125.0, 116.0], n_flat=30)
        events, s = run_backtest_v4(prices)
        assets = s['final_value'] + s['cash']
        self.assertTrue(approx(s['total_profit'], assets - s['total_invested']))
        self.assertEqual(s['n_events'], len(events))
        self.assertTrue(s['years'] > 0)


class TestXIRR(unittest.TestCase):
    def test_one_year_ten_percent(self):
        from tasks.backtest_kc50_dca_v4_1 import _xirr
        d0 = date(2020, 1, 1)
        cf = [(d0, -100.0), (d0 + timedelta(days=365), 110.0)]
        self.assertTrue(approx(_xirr(cf), 0.10, 1e-4))


if __name__ == '__main__':
    unittest.main(verbosity=2)
