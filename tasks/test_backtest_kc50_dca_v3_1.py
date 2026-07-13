#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测 V3 引擎 单元测试 (TDD: 先于实现)。

用合成价格序列验证 run_backtest_v3 的状态机, 不依赖数据库。

V3 相对 V2 的策略变更:
  - 正常止盈 9 档(10%~50%, 步长 5%), 卖比 = 2×档位(10%卖20%、15%卖30%…50%卖100%清仓)
  - 重装阈值 L−2.5%(V2 为 L−5%)
  - DCA 再触发推广到所有非封顶档位(10%~45%), 在 [L, L+5%) 震荡达半额再卖一次同档
  - 50% 档封顶清仓(不再"永不空仓")

关键验证点:
  - 各档卖出比例 = 2×档位; 50% 档清仓; 45% 档仍留底仓
  - 重装阈值 L−2.5%(10% 跌破 7.5% 重装、15% 跌破 12.5% 重装但 10% 不重装)
  - DCA 再触发(10% 档 [10%,15%) / 15% 档 [15%,20%) 震荡达半额再触发)
  - 按档位独立追踪(20% 触发不重置 15% 的 DCA 累计)
  - XIRR、汇总恒等式

运行: conda run -n personal-finance python -m unittest tasks.test_backtest_kc50_dca_v3
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca_v3_1 import (
    run_backtest_v3, DAILY_INVEST, TIER_STEP, FIRST_TIER, REARM_OFFSET,
    TIER_SELL_FRAC,
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
        self.assertTrue(approx(FIRST_TIER, 0.10))
        self.assertTrue(approx(TIER_STEP, 0.05))
        self.assertTrue(approx(REARM_OFFSET, 0.025))
        # 卖比 = 2×档位: 10%->20%, 15%->30%, …, 50%->100%
        self.assertTrue(approx(TIER_SELL_FRAC[0.10], 0.20))
        self.assertTrue(approx(TIER_SELL_FRAC[0.15], 0.30))
        self.assertTrue(approx(TIER_SELL_FRAC[0.20], 0.40))
        self.assertTrue(approx(TIER_SELL_FRAC[0.25], 0.50))
        self.assertTrue(approx(TIER_SELL_FRAC[0.30], 0.60))
        self.assertTrue(approx(TIER_SELL_FRAC[0.35], 0.70))
        self.assertTrue(approx(TIER_SELL_FRAC[0.40], 0.80))
        self.assertTrue(approx(TIER_SELL_FRAC[0.45], 0.90))
        self.assertTrue(approx(TIER_SELL_FRAC[0.50], 1.00))


class TestFlatMarket(unittest.TestCase):
    def test_no_trigger(self):
        prices = make_prices([], n_flat=50)
        events, s = run_backtest_v3(prices)
        self.assertEqual(events, [])
        self.assertEqual(s['n_events'], 0)
        self.assertTrue(approx(s['total_return'], 0.0))


class TestSellFraction10pct(unittest.TestCase):
    def test_fires_once_sells_20pct(self):
        # 100 天 @100, 第 101 天 @112 -> 收益率≈12%(>=10%, <15%), 仅 10% 档, 卖 20%
        prices = make_prices([112.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e['tier'], '10%')
        self.assertEqual(e['trigger'], 'normal')
        self.assertTrue(approx(e['shares_sold'], e['shares_before'] * 0.20))
        self.assertTrue(approx(e['shares_after'], e['shares_before'] * 0.80))
        # 平均成本法: 比例结转, 卖出后平均成本不变
        self.assertTrue(approx(e['cost_before'] / e['shares_before'],
                               e['cost_after'] / e['shares_after']))
        self.assertTrue(approx(e['sell_proceeds'], e['shares_sold'] * e['price']))


class TestSellFraction15pct(unittest.TestCase):
    def test_fires_once_sells_30pct(self):
        # @118 -> 收益率≈18%(>=15%, <20%), 触发 10%(卖20%) + 15%(卖30%)
        prices = make_prices([118.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertEqual(tiers_of(events), ['10%', '15%'])
        e15 = events[1]
        self.assertTrue(approx(e15['shares_sold'], e15['shares_before'] * 0.30))
        self.assertTrue(approx(e15['shares_after'], e15['shares_before'] * 0.70))


class TestClearAtFiftyPct(unittest.TestCase):
    def test_clears_position_at_50pct(self):
        # @160 -> 收益率≈59%(>=50%), 触发 10%~50%, 50% 档卖 100% 清仓
        # (注: @150 因当日定投稀释, 收益率仅 49.5% 达不到 50%, 故用 @160)
        prices = make_prices([160.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertTrue(len(events) >= 1)
        last = events[-1]
        self.assertEqual(last['tier'], '50%')
        self.assertTrue(approx(last['shares_sold'], last['shares_before']))  # 卖全部
        self.assertTrue(approx(last['shares_after'], 0.0))                  # 清仓


class TestNeverEmptyAtFortyFive(unittest.TestCase):
    def test_keeps_position_below_50pct(self):
        # @146 -> 收益率≈46%(>=45%, <50%), 触发 10%~45%, 50% 不触发, 仍留底仓
        prices = make_prices([146.0], n_flat=100)
        events, s = run_backtest_v3(prices)
        self.assertNotIn('50%', tiers_of(events))
        self.assertIn('45%', tiers_of(events))
        self.assertTrue(s['final_shares'] > 0, f"45% 档未清仓应留底仓: {s['final_shares']}")


class TestRearmBelowLMinus2_5:
    """重装阈值 L−2.5%。"""

    class _TenPct(unittest.TestCase):
        def test_rearm_10pct_below_7_5pct(self):
            # @112(12%, 触发10%) -> @107(7%, 跌破7.5%重装10%) -> @112(12%, 再触发10% normal)
            prices = make_prices([112.0, 107.0, 112.0], n_flat=100)
            events, s = run_backtest_v3(prices)
            self.assertEqual(tiers_of(events), ['10%', '10%'])
            self.assertEqual(triggers_of(events), ['normal', 'normal'])

    class _FifteenPct(unittest.TestCase):
        def test_rearm_15pct_not_10pct(self):
            # @118(18%, 触发10%+15%) -> @112(12%, 跌破12.5%重装15%, 但12%>7.5%不重装10%)
            #    -> @118(18%, 10%未重装不触发, 15%重装后触发)
            prices = make_prices([118.0, 112.0, 118.0], n_flat=100)
            events, s = run_backtest_v3(prices)
            self.assertEqual(tiers_of(events), ['10%', '15%', '15%'])
            self.assertEqual(triggers_of(events), ['normal', 'normal', 'normal'])


class TestDcaRetrigger10pct(unittest.TestCase):
    def test_dca_retrigger_at_10pct_band(self):
        # @112(触发10%, 卖20%) -> @114×25 在[10%,15%)震荡, 定投累计达上次卖出额一半再触发10%
        prices = make_prices([112.0] + [114.0] * 25, n_flat=100)
        events, s = run_backtest_v3(prices)
        dca_10 = [e for e in events if e['tier'] == '10%' and e['trigger'] == 'dca_retrigger']
        self.assertTrue(len(dca_10) >= 1, f"应至少 1 次 10% DCA 再触发: {tiers_of(events)}")
        # DCA 再触发时, 自该档上次减仓累计定投 >= 该档上次卖出额一半
        e1 = events[0]  # 首次 10% normal
        e2 = dca_10[0]
        self.assertTrue(e2['dca_at_trigger'] >= e1['sell_proceeds'] / 2.0 - 1e-6)


class TestDcaRetrigger15pct(unittest.TestCase):
    def test_dca_retrigger_at_15pct_band(self):
        # @117(触发10%+15%) -> @120×18 在[15%,20%)震荡, 15% DCA 再触发
        prices = make_prices([117.0] + [120.0] * 18, n_flat=100)
        events, s = run_backtest_v3(prices)
        # @117 先触发 10% 再 15%; 随后 15% 在 [15%,20%) DCA 再触发
        self.assertEqual(events[0]['tier'], '10%')
        self.assertEqual(events[1]['tier'], '15%')
        dca_15 = [e for e in events if e['tier'] == '15%' and e['trigger'] == 'dca_retrigger']
        self.assertTrue(len(dca_15) >= 1, f"应至少 1 次 15% DCA 再触发: {tiers_of(events)}")
        e15_first = events[1]
        self.assertTrue(dca_15[0]['dca_at_trigger'] >= e15_first['sell_proceeds'] / 2.0 - 1e-6)


class TestDcaPerTierIsolation(unittest.TestCase):
    def test_20pct_fire_does_not_reset_15pct_dca(self):
        """20% 档触发不应重置 15% 档的 DCA 累计(按档位独立追踪)。

        白盒: 用 V3Engine 喂 [@117, @120×5, @130],
        @117 触发 10%+15%(建立 15% 的 proceeds 与 dca=0),
        @120×5 让 15% 的 dca 累计(未达半额, 不触发),
        @130 触发 20%(建立 20% 自己的 proceeds, 重置 20% 的 dca)。
        断言: 15% 的 proceeds 与 dca 累计均未被 20% 触发影响。
        """
        from tasks.backtest_kc50_dca_v3_1 import V3Engine
        prices = make_prices([117.0] + [120.0] * 5 + [130.0], n_flat=100)
        eng = V3Engine()
        for d, p in prices:
            eng.step(d, p)

        # 10%/15%/20% 均已触发(disarmed)
        self.assertFalse(eng.armed[0.15])
        self.assertFalse(eng.armed[0.20])

        p15_proceeds = eng.last_sell_proceeds[0.15]
        p20_proceeds = eng.last_sell_proceeds[0.20]
        self.assertTrue(p15_proceeds > 0, "15% 档应有上次卖出额")
        self.assertTrue(p20_proceeds > 0, "20% 档应有上次卖出额")
        # 两档各自独立的卖出额(20% 卖 40% 作用在 10%/15% 减仓后的更小持仓上, 与 15% 卖 30% 额不同)
        self.assertNotEqual(p15_proceeds, p20_proceeds)

        # 关键: 20% 触发只重置 20% 自己的 dca, 不影响 15% 的 dca 累计
        self.assertTrue(eng.dca_since_last_sell[0.15] > 0,
                        "15% 的 DCA 累计应保留(自 @117 起累计 6 天定投)")
        self.assertTrue(approx(eng.dca_since_last_sell[0.20], 0.0),
                        "20% 触发后该档 DCA 累计应重置为 0")

    def test_dca_state_is_per_tier_dict(self):
        """各档 last_sell_proceeds 独立: 触发 10% 不影响 15% 的 proceeds(仍为 0)。"""
        from tasks.backtest_kc50_dca_v3_1 import V3Engine
        prices = make_prices([112.0], n_flat=100)  # 仅触发 10%
        eng = V3Engine()
        for d, p in prices:
            eng.step(d, p)
        self.assertTrue(eng.last_sell_proceeds[0.10] > 0)
        self.assertTrue(approx(eng.last_sell_proceeds[0.15], 0.0))  # 15% 未触发, 保持 0
        self.assertTrue(approx(eng.last_sell_proceeds[0.20], 0.0))


class TestSummarySanity(unittest.TestCase):
    def test_total_profit_identity(self):
        prices = make_prices([112.0, 108.0, 125.0, 116.0], n_flat=30)
        events, s = run_backtest_v3(prices)
        assets = s['final_value'] + s['cash']
        self.assertTrue(approx(s['total_profit'], assets - s['total_invested']))
        self.assertEqual(s['n_events'], len(events))
        self.assertTrue(s['years'] > 0)


class TestXIRR(unittest.TestCase):
    def test_one_year_ten_percent(self):
        from tasks.backtest_kc50_dca_v3_1 import _xirr
        d0 = date(2020, 1, 1)
        cf = [(d0, -100.0), (d0 + timedelta(days=365), 110.0)]
        self.assertTrue(approx(_xirr(cf), 0.10, 1e-4))


if __name__ == '__main__':
    unittest.main(verbosity=2)
