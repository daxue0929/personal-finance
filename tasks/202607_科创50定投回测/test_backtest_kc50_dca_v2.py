#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测 V2 引擎 单元测试 (TDD: 先于实现)。

用合成价格序列验证 run_backtest_v2 的状态机, 不依赖数据库。
关键验证点:
  - 15% 档触发卖 30%、平均成本不变
  - 20%/25% 阶梯触发; 大涨触发多档仍永不空仓
  - DCA 再触发(15%~20% 震荡, 加仓达上次卖出额一半 -> 再卖一次 15%)
  - 跌破 10% 重装 15%
  - 跌破 15% 重装 20% 且 15% 被跳过(字面按档位重装)
  - XIRR、汇总恒等式

运行: conda run -n personal-finance python -m unittest tasks.test_backtest_kc50_dca_v2
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca_v2 import run_backtest_v2, DAILY_INVEST, TIER_STEP, FIRST_TIER


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
        self.assertTrue(approx(FIRST_TIER, 0.15))
        self.assertTrue(approx(TIER_STEP, 0.05))


class TestFlatMarket(unittest.TestCase):
    def test_no_trigger(self):
        prices = make_prices([], n_flat=50)
        events, s = run_backtest_v2(prices)
        self.assertEqual(events, [])
        self.assertEqual(s['n_events'], 0)
        self.assertTrue(approx(s['total_return'], 0.0))


class TestFifteenPctTier(unittest.TestCase):
    def test_fires_once_sells_30pct_avg_cost_unchanged(self):
        # 100 天 @100, 第 101 天 @118 -> 收益率≈17.82%(>=15%, <20%), 仅 15% 档
        prices = make_prices([118.0], n_flat=100)
        events, s = run_backtest_v2(prices)
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


class TestLadderAndNeverEmpty(unittest.TestCase):
    def test_20pct_after_15pct(self):
        # @125 -> 收益率≈24.75%: 15% 与 20% 同日触发, 25% 不触发
        prices = make_prices([125.0], n_flat=100)
        events, s = run_backtest_v2(prices)
        self.assertEqual(tiers_of(events), ['15%', '20%'])
        self.assertTrue(s['final_shares'] > 0)   # 永不空仓

    def test_25pct_fires(self):
        # @131 -> 收益率≈30.69%: 15/20/25/30% 触发
        prices = make_prices([131.0], n_flat=100)
        events, s = run_backtest_v2(prices)
        self.assertIn('25%', tiers_of(events))
        self.assertEqual(len(events), 4)
        self.assertTrue(s['final_shares'] > 0)

    def test_never_empty_on_huge_rise(self):
        # @200 -> 收益率≈99%: 15%~95% 共 17 档触发, 仍留底仓(0.7^17>0)
        prices = make_prices([200.0], n_flat=100)
        events, s = run_backtest_v2(prices)
        self.assertEqual(s['n_events'], 17)
        self.assertTrue(s['final_shares'] > 0, f"持仓不应清零: {s['final_shares']}")


class TestDcaRetrigger(unittest.TestCase):
    def test_dca_retrigger_at_15pct_band(self):
        # 100 天 @100 -> @117(15% 触发) -> 18 天 @120(15%~20% 震荡, DCA 达半触发)
        prices = make_prices([117.0] + [120.0] * 18, n_flat=100)
        events, s = run_backtest_v2(prices)
        self.assertEqual(tiers_of(events), ['15%', '15%'])
        self.assertEqual(triggers_of(events), ['normal', 'dca_retrigger'])
        # 第二次为 DCA 再触发: 触发时累计加仓 >= 上次卖出额一半
        e1, e2 = events
        self.assertTrue(e2['dca_at_trigger'] >= e1['sell_proceeds'] / 2 - 1e-6)


class TestDipRearmFifteen(unittest.TestCase):
    def test_rearm_below_10pct(self):
        # @117(15%触发) -> @105(跌破10%重装15%) -> @120(再触发15%, normal)
        prices = make_prices([117.0, 105.0, 120.0], n_flat=100)
        events, s = run_backtest_v2(prices)
        self.assertEqual(tiers_of(events), ['15%', '15%'])
        self.assertEqual(triggers_of(events), ['normal', 'normal'])


class TestDipRearmTwentySkipFifteen(unittest.TestCase):
    def test_rearm_20pct_skip_15pct(self):
        # @125(15%+20%触发) -> @112(跌破15%仅重装20%, 15%不重装) -> @125(只触发20%, 15%被跳过)
        prices = make_prices([125.0, 112.0, 125.0], n_flat=100)
        events, s = run_backtest_v2(prices)
        self.assertEqual(tiers_of(events), ['15%', '20%', '20%'])
        # 第三次只有 20%, 15% 被跳过(字面按档位重装)
        self.assertEqual(events[2]['tier'], '20%')
        self.assertEqual(events[2]['trigger'], 'normal')


class TestSummarySanity(unittest.TestCase):
    def test_total_profit_identity(self):
        prices = make_prices([118.0, 108.0, 125.0, 116.0], n_flat=30)
        events, s = run_backtest_v2(prices)
        assets = s['final_value'] + s['cash']
        self.assertTrue(approx(s['total_profit'], assets - s['total_invested']))
        self.assertEqual(s['n_events'], len(events))
        self.assertTrue(s['years'] > 0)
        # 永不空仓: 任何时刻持仓份额 > 0
        self.assertTrue(s['final_shares'] > 0)


class TestXIRR(unittest.TestCase):
    def test_one_year_ten_percent(self):
        from tasks.backtest_kc50_dca_v2 import _xirr
        d0 = date(2020, 1, 1)
        cf = [(d0, -100.0), (d0 + timedelta(days=365), 110.0)]
        self.assertTrue(approx(_xirr(cf), 0.10, 1e-4))


if __name__ == '__main__':
    unittest.main(verbosity=2)
