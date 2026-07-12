#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测 V5 引擎 单元测试 (TDD: 先于实现)。

V5 = V4(永不空仓 + DCA 全档 + 分档卖出 + 子弹池复利) + 迟滞重装:
  档位 L 在收益率跌破 L−2.5% 时重装(V4/V3 跌破 L; V2 跌破 L−5%)。
  增加 2.5% 迟滞带, 防止震荡市小幅回撤即重装导致的高频卖出(V3 优化方向 4 落地)。

引擎用 rearm_offset 参数化重装阈值的下偏量:
  - rearm_offset=0.025(V5 默认): 跌破 L−2.5%
  - rearm_offset=0.0: 跌破 L(=V4 opt6=True)
  - rearm_offset=0.05: 跌破 L−5%(=V2 opt6=False)

关键验证点:
  - 常量 REARM_OFFSET_V5 = 0.025
  - 迟滞带 [L−2.5%, L) 内不重装: @114(14%) V5 跳过 15%(V4 重装)
  - 跌破迟滞带重装: @111(11%) V5 重装 15%(V2 跳过)
  - 震荡市 V5 止盈次数 ≤ V4, 15% 档严格减少(迟滞减少高频卖出 -- 用户核心诉求)
  - 回归: rearm_offset=0.0, reinvest=False == V4(opt6=True)
  - 回归: rearm_offset=0.05, opt3=opt8=False, reinvest=False == V2
  - 永不空仓、总收益恒等式、子弹池继承、外部本金不变

运行: data-crawler/venv/bin/python -m unittest tasks.test_backtest_kc50_dca_v5
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca_v5 import (
    run_backtest_v5, REARM_OFFSET_V5, DAILY_INVEST,
)
from tasks.backtest_kc50_dca_v4 import run_backtest_v4
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


class TestConstants(unittest.TestCase):
    def test_params(self):
        self.assertTrue(approx(REARM_OFFSET_V5, 0.025))
        self.assertTrue(approx(DAILY_INVEST, 300.0))


class TestRearmHysteresis(unittest.TestCase):
    """迟滞带: 跌破 L−2.5% 才重装; [L−2.5%, L) 内不重装。"""

    def test_hysteresis_band_skips_15pct_rearm(self):
        # @125(25%, 触发15%+20%) -> @114(14%∈[12.5%,15%), 跌破15%但未跌破12.5%)
        # V5: 15%不重装(迟滞带内), 20%重装(14%<17.5%); 回升@125只触发20%
        prices = make_prices([125.0, 114.0, 125.0], n_flat=100)
        events, s, _ = run_backtest_v5(prices, reinvest=False)
        self.assertEqual(tiers_of(events), ['15%', '20%', '20%'])

    def test_below_hysteresis_band_rearms_15pct(self):
        # @125(触发15%+20%) -> @111(11%∈[10%,12.5%), 跌破12.5%)
        # V5: 15%重装(11%<12.5%), 20%重装; 回升@125触发15%+20%
        prices = make_prices([125.0, 111.0, 125.0], n_flat=100)
        events, s, _ = run_backtest_v5(prices, reinvest=False)
        self.assertEqual(tiers_of(events), ['15%', '20%', '15%', '20%'])


class TestHysteresisScenarioCalibration(unittest.TestCase):
    """确认对照场景下 V4/V2 行为符合预期, 佐证 V5 阈值介于二者之间。"""

    def test_v4_rearms_15pct_at_114(self):
        # V4(跌破L=15%): @114(14%<15%)重装15%, 回升触发15%+20%
        prices = make_prices([125.0, 114.0, 125.0], n_flat=100)
        ev4, _, _ = run_backtest_v4(prices, reinvest=False)
        self.assertEqual(tiers_of(ev4), ['15%', '20%', '15%', '20%'])

    def test_v2_skips_15pct_at_111(self):
        # V2(跌破L-5%=10%): @111(11%>10%)不重装15%, 回升只触发20%
        prices = make_prices([125.0, 111.0, 125.0], n_flat=100)
        ev2, _ = run_backtest_v2(prices)
        self.assertEqual(tiers_of(ev2), ['15%', '20%', '20%'])


class TestHysteresisReducesChurn(unittest.TestCase):
    """用户核心诉求: 迟滞带减少震荡市高频卖出。"""

    def test_v5_fewer_events_than_v4_in_chop(self):
        # 反复 @125(触发)->@114(小幅回撤) 震荡: V4 每轮重装15%+20%再触发,
        # V5 因 14%∈[12.5%,15%) 不重装15%, 每轮只重装20% -> 15%档触发大幅减少
        tail = [125.0, 114.0, 125.0, 114.0, 125.0, 114.0, 125.0]
        prices = make_prices(tail, n_flat=100)
        _, s4, _ = run_backtest_v4(prices, reinvest=False)
        _, s5, _ = run_backtest_v5(prices, reinvest=False)
        self.assertLessEqual(s5['n_events'], s4['n_events'],
                             f"V5止盈应≤V4: V5={s5['n_events']}, V4={s4['n_events']}")
        # 15% 档触发次数 V5 严格少于 V4(迟滞带主要抑制 15% 档高频重装)
        self.assertLess(s5['tier_counts'].get('15%', 0), s4['tier_counts'].get('15%', 0),
                        f"V5的15%档应少于V4: V5={s5['tier_counts'].get('15%',0)}, "
                        f"V4={s4['tier_counts'].get('15%',0)}")


class TestRegressionVsV4(unittest.TestCase):
    def test_zero_offset_reproduces_v4(self):
        # rearm_offset=0.0(跌破L) 且 reinvest=False 应精确复现 V4(opt6=True, reinvest=False)
        prices = make_prices([118.0, 108.0, 125.0, 116.0, 140.0, 90.0, 130.0, 85.0, 150.0, 80.0], n_flat=100)
        _, s4, _ = run_backtest_v4(prices, reinvest=False)
        _, s5, _ = run_backtest_v5(prices, rearm_offset=0.0, reinvest=False)
        self.assertEqual(s5['n_events'], s4['n_events'])
        self.assertEqual(s5['tier_counts'], s4['tier_counts'])
        self.assertEqual(s5['trigger_counts'], s4['trigger_counts'])
        self.assertTrue(approx(s5['total_return'], s4['total_return']))
        self.assertTrue(approx(s5['xirr'], s4['xirr']))
        self.assertTrue(approx(s5['cum_realized'], s4['cum_realized']))
        self.assertTrue(approx(s5['total_sell_proceeds'], s4['total_sell_proceeds']))
        self.assertTrue(approx(s5['final_value'], s4['final_value']))
        self.assertTrue(approx(s5['final_shares'], s4['final_shares']))
        self.assertTrue(approx(s5['bullet_pool'], s4['bullet_pool']))


class TestRegressionVsV2(unittest.TestCase):
    def test_v2_offset_reproduces_v2(self):
        # rearm_offset=0.05(跌破L-5%) 且 opt3=opt8=False, reinvest=False 应复现 V2
        prices = make_prices([118.0, 108.0, 125.0, 116.0, 140.0, 90.0, 130.0], n_flat=40)
        _, s2 = run_backtest_v2(prices)
        _, s5, _ = run_backtest_v5(prices, opt3=False, opt8=False, rearm_offset=0.05, reinvest=False)
        self.assertEqual(s5['n_events'], s2['n_events'])
        self.assertEqual(s5['tier_counts'], s2['tier_counts'])
        self.assertTrue(approx(s5['total_return'], s2['total_return']))
        self.assertTrue(approx(s5['xirr'], s2['xirr']))
        self.assertTrue(approx(s5['cum_realized'], s2['cum_realized']))
        self.assertTrue(approx(s5['total_sell_proceeds'], s2['total_sell_proceeds']))
        self.assertTrue(approx(s5['final_value'], s2['final_value']))


class TestNeverEmpty(unittest.TestCase):
    def test_huge_rise_keeps_position(self):
        # @200 -> 收益率≈99%: 多档触发, 仍留底仓(各档保留率乘积 > 0)
        prices = make_prices([200.0], n_flat=100)
        _, s, _ = run_backtest_v5(prices, reinvest=False)
        self.assertTrue(s['final_shares'] > 0, f"持仓不应清零: {s['final_shares']}")


class TestTotalProfitIdentity(unittest.TestCase):
    def test_identity(self):
        prices = make_prices([120.0, 90.0, 130.0, 80.0, 140.0, 85.0, 150.0], n_flat=80)
        _, s, _ = run_backtest_v5(prices, reinvest=True)
        self.assertTrue(approx(s['total_profit'], s['final_value'] + s['bullet_pool'] - s['total_invested']))
        self.assertTrue(s['final_shares'] > 0)
        self.assertTrue(s['years'] > 0)


class TestBulletPoolInherited(unittest.TestCase):
    def test_reinvest_buys_extra_at_low_day(self):
        # 子弹池复利继承自 V4: 低位(d≤-8%)从池中再投
        prices = make_prices([120.0, 90.0], n_flat=80)
        _, s_on, _ = run_backtest_v5(prices, reinvest=True)
        _, s_off, _ = run_backtest_v5(prices, reinvest=False)
        self.assertEqual(s_on['n_events'], s_off['n_events'])  # @120 高位无再投, 止盈一致
        self.assertTrue(s_on['final_shares'] > s_off['final_shares'])
        self.assertTrue(s_on['bullet_pool'] < s_off['bullet_pool'])
        self.assertTrue(s_on['cum_reinvested'] > 0)


class TestExternalCapitalUnchanged(unittest.TestCase):
    def test_no_ma_weighting_external_principal(self):
        # V5 不引入均线加权定投: 外部本金 == 300 * 交易日数(与 V4 一致)
        prices = make_prices([120.0, 90.0, 130.0, 80.0, 140.0, 85.0], n_flat=80)
        _, s_on, _ = run_backtest_v5(prices, reinvest=True)
        _, s_off, _ = run_backtest_v5(prices, reinvest=False)
        self.assertTrue(approx(s_on['total_invested'], DAILY_INVEST * len(prices)))
        self.assertTrue(approx(s_off['total_invested'], DAILY_INVEST * len(prices)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
