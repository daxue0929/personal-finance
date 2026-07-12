#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50 定投止盈回测 V4 引擎 单元测试 (TDD: 先于实现)。

V4 = V3(opt3/6/8 永不空仓 + DCA 全档 + 跌破重装 + 分档卖出) + 优化1(子弹池复利)。
用合成价格序列验证 run_backtest_v4 的状态机, 不依赖数据库。
关键验证点:
  - 常量: MA_WINDOW / MA_WARMUP / REINVEST_D_THRESHOLD / REINVEST_MULT / REINVEST_MULT_DEEP / POOL_DRAIN_FRAC
  - _reinvest_mult: d≤-20%->5x · -20%<d≤-8%->3x · d>-8%->0
  - _reinvest_target: pool*2% + dca_amount*mult
  - 优化1 核心行为: 低位(d≤-8%)从子弹池再投(份额↑、池↓、cum_reinvested>0)
  - d > -8% 不触发再投(池==全部回款)
  - 仅优化1、不含均线加权定投: 外部本金 == DAILY_INVEST * 交易日数(与 V3 一致)
  - 子弹池不过零(再投 min(pool, target) 封顶)
  - 总收益恒等式: total_profit == final_value + bullet_pool - total_invested
  - 深跌(5x)再投额 > 浅跌(3x)
  - 回归: reinvest=False 精确复现 V3; reinvest=False 且 opt 全关 复现 V2

运行: data-crawler/venv/bin/python -m unittest tasks.test_backtest_kc50_dca_v4
"""
import math
import unittest
from datetime import date, timedelta

from tasks.backtest_kc50_dca_v4 import (
    run_backtest_v4, _reinvest_mult, _reinvest_target,
    DAILY_INVEST,
    MA_WINDOW, MA_WARMUP,
    REINVEST_D_THRESHOLD, REINVEST_MULT, REINVEST_MULT_DEEP, POOL_DRAIN_FRAC,
)
from tasks.backtest_kc50_dca_v3 import run_backtest_v3
from tasks.backtest_kc50_dca_v2 import run_backtest_v2


def _dates(n, start=date(2020, 1, 1)):
    return [start + timedelta(days=i) for i in range(n)]


def make_prices(tail, n_flat=100, flat_price=100.0):
    """前 n_flat 天恒定 flat_price(累积底仓, 平均成本≈flat_price), 后接 tail。"""
    full = [flat_price] * n_flat + list(tail)
    return list(zip(_dates(len(full)), full))


def approx(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


class TestConstants(unittest.TestCase):
    def test_params(self):
        self.assertEqual(MA_WINDOW, 250)
        self.assertEqual(MA_WARMUP, 60)
        self.assertTrue(approx(REINVEST_D_THRESHOLD, -0.08))
        self.assertTrue(approx(REINVEST_MULT, 3.0))
        self.assertTrue(approx(REINVEST_MULT_DEEP, 5.0))
        self.assertTrue(approx(POOL_DRAIN_FRAC, 0.02))
        self.assertTrue(approx(DAILY_INVEST, 300.0))


class TestReinvestMult(unittest.TestCase):
    def test_deep_shallow_none(self):
        self.assertTrue(approx(_reinvest_mult(-0.30), 5.0))   # d≤-20%: 5x
        self.assertTrue(approx(_reinvest_mult(-0.20), 5.0))   # 边界 -20%: 5x
        self.assertTrue(approx(_reinvest_mult(-0.199), 3.0))  # -20%<d≤-8%: 3x
        self.assertTrue(approx(_reinvest_mult(-0.10), 3.0))
        self.assertTrue(approx(_reinvest_mult(-0.08), 3.0))   # 边界 -8%: 3x
        self.assertTrue(approx(_reinvest_mult(-0.079), 0.0))  # d>-8%: 不触发
        self.assertTrue(approx(_reinvest_mult(0.05), 0.0))
        self.assertTrue(approx(_reinvest_mult(0.20), 0.0))

    def test_target_formula(self):
        # target = pool*POOL_DRAIN_FRAC + dca_amount*mult
        self.assertTrue(approx(_reinvest_target(10000.0, 300.0, -0.10),
                               10000.0 * 0.02 + 300.0 * 3.0))
        self.assertTrue(approx(_reinvest_target(10000.0, 300.0, -0.30),
                               10000.0 * 0.02 + 300.0 * 5.0))
        self.assertTrue(approx(_reinvest_target(10000.0, 300.0, 0.05),
                               10000.0 * 0.02 + 300.0 * 0.0))


class TestBulletPoolDeploy(unittest.TestCase):
    def test_reinvest_buys_extra_at_low_day(self):
        # 80 天 @100(warmup 满足, MA≈100) -> @120(收益+20%, 15%+20% 触发, 回款入池)
        # -> @90(d≈-10% ≤ -8%, 从子弹池再投)
        prices = make_prices([120.0, 90.0], n_flat=80)
        _, s_on, _ = run_backtest_v4(prices, reinvest=True)
        _, s_off, _ = run_backtest_v4(prices, reinvest=False)
        # @120 高位无再投, 两者止盈一致
        self.assertEqual(s_on['n_events'], s_off['n_events'])
        # 再投: 份额更多、子弹池更少、累计再投>0
        self.assertTrue(s_on['final_shares'] > s_off['final_shares'],
                        f"再投后期末份额应更大: {s_on['final_shares']} vs {s_off['final_shares']}")
        self.assertTrue(s_on['bullet_pool'] < s_off['bullet_pool'])
        self.assertTrue(s_on['cum_reinvested'] > 0)
        # 外部本金不变(仅优化1, 不含均线加权定投)
        self.assertTrue(approx(s_on['total_invested'], DAILY_INVEST * len(prices)))

    def test_no_reinvest_when_d_above_minus8(self):
        # @120 触发止盈入池 -> @105(d≈+4.7% > -8%, 不再投)
        prices = make_prices([120.0, 105.0], n_flat=80)
        _, s, _ = run_backtest_v4(prices, reinvest=True)
        self.assertTrue(approx(s['cum_reinvested'], 0.0))
        # 子弹池 == 全部回款(未消耗)
        self.assertTrue(approx(s['bullet_pool'], s['total_sell_proceeds']))


class TestExternalCapitalUnchanged(unittest.TestCase):
    def test_no_ma_weighting_external_principal(self):
        # 仅优化1: 每日固定 300, 不引入均线加权定投 -> 外部本金 == 300 * 交易日数
        prices = make_prices([120.0, 90.0, 130.0, 80.0, 140.0, 85.0], n_flat=80)
        _, s_on, _ = run_backtest_v4(prices, reinvest=True)
        _, s_off, _ = run_backtest_v4(prices, reinvest=False)
        self.assertTrue(approx(s_on['total_invested'], DAILY_INVEST * len(prices)))
        self.assertTrue(approx(s_off['total_invested'], DAILY_INVEST * len(prices)))


class TestPoolNeverNegative(unittest.TestCase):
    def test_drain_capped_at_pool_balance(self):
        # @120 大额入池 -> 30 天 @90 持续低估, 池子被抽但不过零
        prices = make_prices([120.0] + [90.0] * 30, n_flat=80)
        _, s, _ = run_backtest_v4(prices, reinvest=True)
        self.assertTrue(s['bullet_pool'] >= -1e-9, f"子弹池不应为负: {s['bullet_pool']}")
        self.assertTrue(s['cum_reinvested'] > 0)
        # 再投总额不可能超过累计回款(再投 min(pool, target) 封顶)
        self.assertTrue(s['cum_reinvested'] <= s['total_sell_proceeds'] + 1e-6)


class TestTotalProfitIdentity(unittest.TestCase):
    def test_identity(self):
        prices = make_prices([120.0, 90.0, 130.0, 80.0, 140.0, 85.0, 150.0], n_flat=80)
        _, s, _ = run_backtest_v4(prices, reinvest=True)
        self.assertTrue(approx(s['total_profit'],
                               s['final_value'] + s['bullet_pool'] - s['total_invested']))
        self.assertTrue(s['final_shares'] > 0)
        self.assertTrue(s['years'] > 0)


class TestDeepVsShallowDeploy(unittest.TestCase):
    def test_deep_dip_deploys_more(self):
        # 同样的入池(@120 止盈) -> 浅跌 @90(3x) vs 深跌 @75(5x), 深跌再投更多
        shallow = make_prices([120.0, 90.0], n_flat=80)
        deep = make_prices([120.0, 75.0], n_flat=80)
        _, s_shallow, _ = run_backtest_v4(shallow, reinvest=True)
        _, s_deep, _ = run_backtest_v4(deep, reinvest=True)
        # @120 入池金额一致(高位无再投, 止盈相同)
        self.assertTrue(approx(s_shallow['total_sell_proceeds'], s_deep['total_sell_proceeds']))
        # 深跌(5x) 再投额 > 浅跌(3x)
        self.assertTrue(s_deep['cum_reinvested'] > s_shallow['cum_reinvested'],
                        f"深跌应再投更多: {s_deep['cum_reinvested']} vs {s_shallow['cum_reinvested']}")


class TestRegressionVsV3(unittest.TestCase):
    def test_reinvest_off_reproduces_v3(self):
        # reinvest=False 时, V4 引擎应与 V3(opt3/6/8=True) 数值完全一致
        # 用 n_flat=100 使 warmup 满足、d 被计算, 验证 d 计算不扰动 V3 数值
        prices = make_prices([118.0, 108.0, 125.0, 116.0, 140.0, 90.0, 130.0, 85.0, 150.0, 80.0],
                             n_flat=100)
        _, s3 = run_backtest_v3(prices)
        _, s4, _ = run_backtest_v4(prices, reinvest=False)
        self.assertEqual(s4['n_events'], s3['n_events'])
        self.assertEqual(s4['tier_counts'], s3['tier_counts'])
        self.assertEqual(s4['trigger_counts'], s3['trigger_counts'])
        self.assertTrue(approx(s4['total_return'], s3['total_return']))
        self.assertTrue(approx(s4['xirr'], s3['xirr']))
        self.assertTrue(approx(s4['cum_realized'], s3['cum_realized']))
        self.assertTrue(approx(s4['total_sell_proceeds'], s3['total_sell_proceeds']))
        self.assertTrue(approx(s4['final_value'], s3['final_value']))
        self.assertTrue(approx(s4['final_shares'], s3['final_shares']))
        self.assertTrue(approx(s4['total_invested'], s3['total_invested']))
        # 子弹池(未再投) == V3 闲置现金
        self.assertTrue(approx(s4['bullet_pool'], s3['cash']))


class TestRegressionVsV2(unittest.TestCase):
    def test_all_off_reproduces_v2(self):
        # reinvest=False 且 opt3/6/8 全关 时, V4 应与 V2 数值完全一致
        prices = make_prices([118.0, 108.0, 125.0, 116.0, 140.0, 90.0, 130.0], n_flat=40)
        _, s2 = run_backtest_v2(prices)
        _, s4, _ = run_backtest_v4(prices, opt3=False, opt6=False, opt8=False, reinvest=False)
        self.assertEqual(s4['n_events'], s2['n_events'])
        self.assertEqual(s4['tier_counts'], s2['tier_counts'])
        self.assertTrue(approx(s4['total_return'], s2['total_return']))
        self.assertTrue(approx(s4['xirr'], s2['xirr']))
        self.assertTrue(approx(s4['cum_realized'], s2['cum_realized']))
        self.assertTrue(approx(s4['total_sell_proceeds'], s2['total_sell_proceeds']))
        self.assertTrue(approx(s4['final_value'], s2['final_value']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
