#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数分析纯计算函数测试（TDD）

测试 app/analytics/index_analysis.py 中的纯计算逻辑，不依赖数据库。
覆盖：均线、年化波动率、年化收益率、涨跌幅分布、月度收益、定投模拟（含一次性买入对比）、均线信号。
"""
import math
import statistics
from datetime import date

import pytest

from app.analytics.index_analysis import (
    calc_moving_average,
    calc_volatility,
    calc_annualized_return,
    calc_change_distribution,
    calc_monthly_returns,
    calc_ma_signal,
    calc_bollinger_bands,
    calc_bollinger_signal,
)


# ==================== 均线 ====================

def test_moving_average_basic():
    closes = [1, 2, 3, 4, 5]
    result = calc_moving_average(closes, 3)
    # 前 2 个不足窗口 -> None；之后为前 3 个的均值
    assert result == [None, None, 2.0, 3.0, 4.0]


def test_moving_average_window_one():
    closes = [1, 2, 3]
    assert calc_moving_average(closes, 1) == [1.0, 2.0, 3.0]


def test_moving_average_window_larger_than_data():
    closes = [1, 2, 3]
    result = calc_moving_average(closes, 5)
    assert result == [None, None, None]


def test_moving_average_empty():
    assert calc_moving_average([], 3) == []


# ==================== 布林带 ====================

def test_bollinger_bands_basic():
    # window=3，标准差用总体标准差（ddof=0）
    closes = [1, 2, 3, 4, 5]
    upper, middle, lower = calc_bollinger_bands(closes, window=3, num_std=2)
    # 前 2 个不足窗口 -> None
    assert upper[:2] == [None, None]
    assert middle[:2] == [None, None]
    # 第 3 点：窗口 [1,2,3]，mean=2，std=√(2/3)≈0.8165
    expected_std = (2 / 3) ** 0.5
    assert middle[2] == pytest.approx(2.0)
    assert upper[2] == pytest.approx(2 + 2 * expected_std)
    assert lower[2] == pytest.approx(2 - 2 * expected_std)
    # 第 5 点：窗口 [3,4,5]，mean=4，std=√(2/3)
    assert middle[4] == pytest.approx(4.0)
    assert upper[4] == pytest.approx(4 + 2 * expected_std)
    assert lower[4] == pytest.approx(4 - 2 * expected_std)
    # 中轨 == MA(window)
    ma = calc_moving_average(closes, 3)
    assert middle == ma


def test_bollinger_bands_default_window():
    closes = list(range(1, 25))  # 24 条
    upper, middle, lower = calc_bollinger_bands(closes)
    # 默认 window=20，前 19 个 None
    assert upper[:19] == [None] * 19
    assert middle[19] is not None
    # 上轨 > 中轨 > 下轨
    assert upper[19] > middle[19] > lower[19]


def test_bollinger_bands_empty():
    upper, middle, lower = calc_bollinger_bands([])
    assert upper == middle == lower == []


def test_bollinger_bands_insufficient_data():
    upper, middle, lower = calc_bollinger_bands([1, 2], window=5)
    assert upper == [None, None]
    assert middle == [None, None]


# ==================== 布林带信号 ====================
# 固定三轨：middle=100, upper=110, lower=90 -> 当前带宽=20%
# bandwidths 取 [10,20,30] -> 当前带宽分位≈33%（中性，不触发带宽提示）

def test_boll_signal_above_upper():
    r = calc_bollinger_signal(115, 110, 100, 90, [10, 20, 30])
    assert r['position'] == 'above_upper'
    assert r['type'] == 'warning'
    assert '突破布林上轨' in r['suggestion']


def test_boll_signal_below_lower():
    r = calc_bollinger_signal(85, 110, 100, 90, [10, 20, 30])
    assert r['position'] == 'below_lower'
    assert r['type'] == 'success'
    assert '跌破布林下轨' in r['suggestion']


def test_boll_signal_near_upper():
    # close=109 >= upper*0.98=107.8
    r = calc_bollinger_signal(109, 110, 100, 90, [10, 20, 30])
    assert r['position'] == 'near_upper'
    assert '压力位' in r['suggestion']


def test_boll_signal_near_lower():
    # close=91 <= lower*1.02=91.8
    r = calc_bollinger_signal(91, 110, 100, 90, [10, 20, 30])
    assert r['position'] == 'near_lower'
    assert '支撑位' in r['suggestion']


def test_boll_signal_middle():
    r = calc_bollinger_signal(100, 110, 100, 90, [10, 20, 30])
    assert r['position'] == 'middle'
    assert r['type'] == 'info'


def test_boll_signal_bandwidth_narrow():
    # 当前带宽=20，区间带宽大多更大 -> 分位<20% -> 收窄
    r = calc_bollinger_signal(100, 110, 100, 90, [40, 40, 40, 40, 20])
    assert r['bandwidth_percentile'] is not None
    assert r['bandwidth_percentile'] < 20
    assert '带宽收窄' in r['suggestion']
    assert '变盘' in r['suggestion']


def test_boll_signal_bandwidth_wide():
    # 当前带宽=20，区间带宽大多更小 -> 分位>80% -> 放大
    r = calc_bollinger_signal(100, 110, 100, 90, [5, 5, 5, 5, 5, 20])
    assert r['bandwidth_percentile'] > 80
    assert '带宽放大' in r['suggestion']


def test_boll_signal_insufficient_data():
    r = calc_bollinger_signal(100, None, None, None, [])
    assert r['position'] is None
    assert '数据不足' in r['suggestion']
    assert r['bandwidth_percentile'] is None
    # 数据不足时无概率推荐
    assert r['buy_prob'] is None and r['sell_prob'] is None


# ----- 买入/卖出概率推荐（连续位置概率 + 带宽分档微调）-----
# 固定三轨 lower=90 / middle=100 / upper=110
# 中性带宽序列 [15, 25]：当前带宽=20，分位=50%（中性档，不偏移），便于验证基准概率
NEUTRAL_BWS = [15, 25]


def test_boll_prob_below_lower_clamped():
    # 跌破下轨：钳制买入85
    r = calc_bollinger_signal(85, 110, 100, 90, NEUTRAL_BWS)
    assert r['buy_prob'] == 85 and r['sell_prob'] == 15


def test_boll_prob_at_lower():
    # 恰在下轨：买入85
    r = calc_bollinger_signal(90, 110, 100, 90, NEUTRAL_BWS)
    assert r['buy_prob'] == 85 and r['sell_prob'] == 15


def test_boll_prob_continuous_rising():
    """区间内价格越高，买入概率越低（连续递减，不再跳档）"""
    probs = [calc_bollinger_signal(p, 110, 100, 90, NEUTRAL_BWS)['buy_prob']
             for p in [91, 93, 95, 97, 100, 103, 105, 107, 109]]
    # 单调不增
    assert all(probs[i] >= probs[i + 1] for i in range(len(probs) - 1))
    # 接近下轨明显大于接近上轨
    assert probs[0] > 70 and probs[-1] < 25


def test_boll_prob_at_middle():
    # 中轨：买入50/卖出50
    r = calc_bollinger_signal(100, 110, 100, 90, NEUTRAL_BWS)
    assert r['buy_prob'] == 50 and r['sell_prob'] == 50


def test_boll_prob_at_upper():
    # 上轨：买入15/卖出85
    r = calc_bollinger_signal(110, 110, 100, 90, NEUTRAL_BWS)
    assert r['buy_prob'] == 15 and r['sell_prob'] == 85


def test_boll_prob_above_upper_clamped():
    # 突破上轨：钳制买入15
    r = calc_bollinger_signal(115, 110, 100, 90, NEUTRAL_BWS)
    assert r['buy_prob'] == 15 and r['sell_prob'] == 85


def test_boll_prob_bandwidth_narrow_pulls_neutral():
    # 收窄档(分位<20%)：拉回中性 50/50，无论位置
    # 接近上轨(base 18) + 收窄 -> 50/50
    r = calc_bollinger_signal(109, 110, 100, 90, [40, 40, 40, 40, 20])
    assert r['bandwidth_percentile'] < 20
    assert r['buy_prob'] == 50 and r['sell_prob'] == 50


def test_boll_prob_bandwidth_wide_amplifies_trend():
    # 放大档(分位>80%)：趋势强劲，向当前方向偏移 ±10
    # 接近上轨(base 18，卖方方向) + 放大 -> 买入8/卖出92
    r = calc_bollinger_signal(109, 110, 100, 90, [5, 5, 5, 5, 5, 20])
    assert r['bandwidth_percentile'] > 80
    assert r['buy_prob'] == 8 and r['sell_prob'] == 92


def test_boll_prob_bandwidth_wide_amplifies_buy_side():
    # 接近下轨(base 82，买方方向) + 放大 -> 偏向买入 +10 -> 买入92/卖出8
    r = calc_bollinger_signal(91, 110, 100, 90, [5, 5, 5, 5, 5, 20])
    assert r['buy_prob'] == 92 and r['sell_prob'] == 8


def test_boll_prob_sums_to_100():
    """任意场景买卖概率之和恒为 100"""
    bws_set = [NEUTRAL_BWS, [40, 40, 40, 40, 20], [5, 5, 5, 5, 5, 20], [18, 22], [12, 28, 35]]
    for price in [85, 90, 91, 95, 100, 105, 109, 110, 115]:
        for bws in bws_set:
            r = calc_bollinger_signal(price, 110, 100, 90, bws)
            assert r['buy_prob'] + r['sell_prob'] == 100, (price, bws, r['buy_prob'], r['sell_prob'])


def test_boll_prob_in_suggestion():
    r = calc_bollinger_signal(115, 110, 100, 90, NEUTRAL_BWS)
    assert '买入推荐：15%' in r['suggestion'] and '卖出推荐：85%' in r['suggestion']


# ==================== 年化波动率 ====================

def test_volatility_known_value():
    change_pcts = [1.0, -1.0, 2.0, 0.5]
    expected = statistics.stdev(change_pcts) * math.sqrt(250)
    result = calc_volatility(change_pcts)
    assert result == pytest.approx(expected, rel=1e-9)


def test_volatility_insufficient_data():
    assert calc_volatility([1.5]) is None
    assert calc_volatility([]) is None


# ==================== 年化收益率 ====================

def test_annualized_return_one_year():
    # 100 -> 121，正好 250 个交易日（1 年）-> 21%
    result = calc_annualized_return(100, 121, 250)
    assert result == pytest.approx(0.21, rel=1e-9)


def test_annualized_return_two_years():
    # 100 -> 121，500 个交易日（2 年）-> sqrt(1.21) - 1
    result = calc_annualized_return(100, 121, 500)
    assert result == pytest.approx(math.sqrt(1.21) - 1, rel=1e-9)


def test_annualized_return_nonpositive_days():
    assert calc_annualized_return(100, 121, 0) is None
    assert calc_annualized_return(100, 121, -10) is None


def test_annualized_return_nonpositive_start():
    assert calc_annualized_return(0, 121, 250) is None


# ==================== 涨跌幅分布 ====================

def test_change_distribution_counts():
    change_pcts = [-2.5, -1.5, 0.5, 1.5, 2.5]
    result = calc_change_distribution(change_pcts, bin_size=1.0)
    # 分箱 [-3,-2),[-2,-1),[-1,0),[0,1),[1,2),[2,3)
    counts = [b['count'] for b in result]
    assert counts == [1, 1, 0, 1, 1, 1]
    # 每个箱有 label / min / max
    for b in result:
        assert 'label' in b and 'min' in b and 'max' in b


def test_change_distribution_empty():
    assert calc_change_distribution([]) == []


def test_change_distribution_bin_size_2():
    change_pcts = [-3, -1, 1, 3]
    result = calc_change_distribution(change_pcts, bin_size=2.0)
    counts = [b['count'] for b in result]
    # 分箱 [-4,-2),[-2,0),[0,2),[2,4)
    assert counts == [1, 1, 1, 1]


# ==================== 月度收益 ====================

def test_monthly_returns_basic():
    dates = ['2024-01-02', '2024-01-09', '2024-02-01', '2024-02-08', '2024-03-01']
    closes = [100, 110, 105, 120, 115]
    result = calc_monthly_returns(dates, closes)
    assert len(result) == 3
    # 1 月：100 -> 110 = 10%
    assert result[0]['year'] == 2024 and result[0]['month'] == 1
    assert result[0]['return_rate'] == pytest.approx(0.10, rel=1e-9)
    # 2 月：105 -> 120
    assert result[1]['return_rate'] == pytest.approx(15 / 105, rel=1e-9)
    # 3 月：115 -> 115 = 0
    assert result[2]['return_rate'] == pytest.approx(0.0, rel=1e-9)
    # label 形如 '2024-01'
    assert result[0]['label'] == '2024-01'


def test_monthly_returns_single_month():
    result = calc_monthly_returns(['2024-01-02', '2024-01-09'], [100, 110])
    assert len(result) == 1
    assert result[0]['return_rate'] == pytest.approx(0.10, rel=1e-9)


def test_monthly_returns_empty():
    assert calc_monthly_returns([], []) == []


# ==================== 均线信号 ====================

def test_ma_signal_below():
    # 最新价低于 MA250 -> 应提示"低于"
    sig = calc_ma_signal(100, ma60=110, ma250=120)
    assert sig['ma60_diff_pct'] == pytest.approx((100 - 110) / 110 * 100, rel=1e-9)
    assert sig['ma250_diff_pct'] == pytest.approx((100 - 120) / 120 * 100, rel=1e-9)
    assert '低于' in sig['suggestion']


def test_ma_signal_above():
    sig = calc_ma_signal(130, ma60=110, ma250=120)
    assert sig['ma60_diff_pct'] > 0
    assert sig['ma250_diff_pct'] > 0
    # 高于均线 -> 提示追高风险或中性偏热
    assert isinstance(sig['suggestion'], str) and len(sig['suggestion']) > 0


def test_ma_signal_none_ma():
    # MA 数据不足（None）-> diff 为 None，suggestion 仍返回字符串
    sig = calc_ma_signal(100, ma60=None, ma250=None)
    assert sig['ma60_diff_pct'] is None
    assert sig['ma250_diff_pct'] is None
    assert isinstance(sig['suggestion'], str)
