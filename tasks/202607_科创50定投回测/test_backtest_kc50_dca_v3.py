#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测 V3 引擎 单元测试 (TDD: 先于实现)。

用合成价格序列验证 run_backtest_v3 的状态机, 不依赖数据库。
关键验证点:
  - 常量: DAILY_INVEST / FIRST_TIER / TIER_STEP / sell_frac 各档
  - 优化8: 15% 卖 20%、25% 卖 40%、30% 卖 50%; 平均成本法不变
  - 阶梯触发 + 大涨连触多档仍永不空仓
  - 优化6: 20% 后回落到 10%~15% 再上涨, 15% 不再被跳过(跌破自身档位重装)
  - 优化3: 高档(20%~25%)震荡区间加仓达半额 -> DCA 再触发 20%
  - 15% 档 DCA 再触发仍工作(向后兼容 V2 行为)
  - 回归: run_backtest_v3(opt3=opt6=opt8=False) 与 V2 数值完全一致
  - 汇总恒等式、永不空仓

运行: data-crawler/venv/bin/python -m unittest tasks.test_backtest_kc50_dca_v3
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca_v3 import (
    run_backtest_v3, sell_frac,
    DAILY_INVEST, FIRST_TIER, TIER_STEP,
    SELL_FRAC_BASE, SELL_FRAC_STEP, SELL_FRAC_CAP,
)
from tasks.backtest_kc50_dca_v2 import run_backtest_v2


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
        self.assertTrue(approx(SELL_FRAC_BASE, 0.20))
        self.assertTrue(approx(SELL_FRAC_STEP, 0.10))
        self.assertTrue(approx(SELL_FRAC_CAP, 0.90))


class TestSellFracByTier(unittest.TestCase):
    def test_opt8_fractions(self):
        # 15%->20%, 20%->30%, 25%->40%, 30%->50%, 35%->60%, 40%->70%
        self.assertTrue(approx(sell_frac(0.15), 0.20))
        self.assertTrue(approx(sell_frac(0.20), 0.30))
        self.assertTrue(approx(sell_frac(0.25), 0.40))
        self.assertTrue(approx(sell_frac(0.30), 0.50))
        self.assertTrue(approx(sell_frac(0.35), 0.60))
        self.assertTrue(approx(sell_frac(0.40), 0.70))

    def test_opt8_cap(self):
        # 高档封顶 90%, 确保单次至少留 10% -> 永不空仓
        self.assertTrue(approx(sell_frac(0.50), 0.90))
        self.assertTrue(approx(sell_frac(0.95), 0.90))
        self.assertTrue(sell_frac(0.95) < 1.0)

    def test_opt8_off_is_v2_30pct(self):
        for L in (0.15, 0.20, 0.30, 0.50):
            self.assertTrue(approx(sell_frac(L, opt8=False), 0.30))


class TestFifteenPctTier(unittest.TestCase):
    def test_fires_sells_20pct_avg_cost_unchanged(self):
        # 100 天 @100, 第 101 天 @118 -> 收益率≈17.82%(>=15%, <20%), 仅 15% 档, 卖 20%
        prices = make_prices([118.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e['tier'], '15%')
        self.assertEqual(e['trigger'], 'normal')
        self.assertTrue(approx(e['sell_frac'], 0.20))
        self.assertTrue(approx(e['shares_sold'], e['shares_before'] * 0.20))
        self.assertTrue(approx(e['shares_after'], e['shares_before'] * 0.80))
        # 平均成本法: 比例结转, 卖出后平均成本不变
        self.assertTrue(approx(e['cost_before'] / e['shares_before'],
                               e['cost_after'] / e['shares_after']))
        self.assertTrue(approx(e['sell_proceeds'], e['shares_sold'] * e['price']))


class TestOpt8HigherTiers(unittest.TestCase):
    def test_25pct_sells_40pct_30pct_sells_50pct(self):
        # @131 -> 收益率≈30.69%: 15/20/25/30% 触发
        prices = make_prices([131.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(tiers_of(events), ['15%', '20%', '25%', '30%'])
        e25 = events[2]
        e30 = events[3]
        self.assertTrue(approx(e25['sell_frac'], 0.40))
        self.assertTrue(approx(e25['shares_sold'], e25['shares_before'] * 0.40))
        self.assertTrue(approx(e30['sell_frac'], 0.50))
        self.assertTrue(approx(e30['shares_sold'], e30['shares_before'] * 0.50))
        self.assertTrue(s['final_shares'] > 0)


class TestLadderAndNeverEmpty(unittest.TestCase):
    def test_20pct_after_15pct(self):
        prices = make_prices([125.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(tiers_of(events), ['15%', '20%'])
        self.assertTrue(s['final_shares'] > 0)

    def test_never_empty_on_huge_rise(self):
        # @200 -> 收益率≈99%: 15%~95% 共 17 档触发, 仍留底仓(各档保留率乘积 > 0)
        prices = make_prices([200.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(s['n_events'], 17)
        self.assertTrue(s['final_shares'] > 0, f"持仓不应清零: {s['final_shares']}")


class TestOpt6NoSkipFifteen(unittest.TestCase):
    def test_rearm_below_own_tier_does_not_skip_15pct(self):
        # @125(15%+20%触发) -> @112(跌破15%: 15%与20%同时重装) -> @125(15%与20%均再触发, 15%不再跳过)
        prices = make_prices([125.0, 112.0, 125.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        # 关键: 第三段回升时 15% 正常触发(V2 会跳过 15%, 只触发 20%)
        self.assertEqual(tiers_of(events), ['15%', '20%', '15%', '20%'])
        self.assertEqual(events[2]['tier'], '15%')
        self.assertEqual(events[2]['trigger'], 'normal')

    def test_opt6_off_reproduces_v2_skip(self):
        # 关闭优化6 时, 退化回 V2 的「跌破 L−5% 重装」, 15% 被跳过
        prices = make_prices([125.0, 112.0, 125.0], n_flat=100)
        events, s = run_backtest_v3(prices, opt6=False)
        self.assertEqual(tiers_of(events), ['15%', '20%', '20%'])


class TestDcaRetriggerFifteen(unittest.TestCase):
    def test_dca_retrigger_at_15pct_band_still_works(self):
        # 100 天 @100 -> @117(15% 触发) -> 18 天 @120(15%~20% 震荡, DCA 达半触发)
        prices = make_prices([117.0] + [120.0] * 18, n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(tiers_of(events), ['15%', '15%'])
        self.assertEqual(triggers_of(events), ['normal', 'dca_retrigger'])
        e1, e2 = events
        self.assertTrue(e2['dca_at_trigger'] >= e1['sell_proceeds'] / 2 - 1e-6)


class TestOpt3HigherTierDca(unittest.TestCase):
    def test_dca_retrigger_at_20pct_band(self):
        # 大底仓(400 天 @100) -> @122(15%+20% 触发, 收益率≈21.9%) -> 缓升尾段
        # 使收益率滞留 [20%,25%) 且累计加仓达 20% 卖出额一半 -> DCA 再触发 20%
        # (平价行情下定投稀释会拉低收益率, 必须缓升才能让收益率留在 20%~25% 区间)
        tail_rise = [122.0 + 0.10 * i for i in range(1, 80)]
        prices = make_prices([122.0] + tail_rise, n_flat=400)
        events, s = run_backtest_v3(prices)
        dca20 = [e for e in events if e['tier'] == '20%' and e['trigger'] == 'dca_retrigger']
        self.assertTrue(len(dca20) >= 1, f"应出现 20% 档 DCA 再触发, 实际: {tiers_of(events)}")
        # DCA 触发时收益率确实在 [20%, 25%)
        self.assertTrue(0.20 <= dca20[0]['profit_rate'] < 0.25)


class TestRegressionVsV2(unittest.TestCase):
    def test_all_off_reproduces_v2(self):
        # 三项优化全关时, V3 引擎应与 V2 数值完全一致
        prices = make_prices([118.0, 108.0, 125.0, 116.0, 140.0, 90.0, 130.0], n_flat=40)
        ev2, s2 = run_backtest_v2(prices)
        ev3, s3 = run_backtest_v3(prices, opt3=False, opt6=False, opt8=False)
        self.assertEqual(s3['n_events'], s2['n_events'])
        self.assertEqual(s3['tier_counts'], s2['tier_counts'])
        self.assertEqual(s3['trigger_counts'], s2['trigger_counts'])
        self.assertTrue(approx(s3['total_return'], s2['total_return']))
        self.assertTrue(approx(s3['xirr'], s2['xirr']))
        self.assertTrue(approx(s3['cum_realized'], s2['cum_realized']))
        self.assertTrue(approx(s3['total_sell_proceeds'], s2['total_sell_proceeds']))
        self.assertTrue(approx(s3['final_value'], s2['final_value']))


class TestSummarySanity(unittest.TestCase):
    def test_total_profit_identity_and_never_empty(self):
        prices = make_prices([118.0, 108.0, 125.0, 116.0, 140.0, 90.0, 130.0], n_flat=30)
        events, s = run_backtest_v3(prices)
        assets = s['final_value'] + s['cash']
        self.assertTrue(approx(s['total_profit'], assets - s['total_invested']))
        self.assertEqual(s['n_events'], len(events))
        self.assertTrue(s['years'] > 0)
        self.assertTrue(s['final_shares'] > 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
