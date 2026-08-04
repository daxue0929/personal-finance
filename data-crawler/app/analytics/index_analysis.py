#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数分析纯计算函数

所有函数不依赖数据库，仅做数值计算，便于单元测试。
输入约定：
- dates：'YYYY-MM-DD' 字符串列表，按日期升序（调用方保证）
- closes / change_pcts：数值列表（int/float/Decimal 均可，内部转 float）
- change_pcts 单位为「百分比数值」，如 1.23 表示 1.23%
"""
import math
import statistics
from datetime import datetime
from typing import List, Optional

import numpy as np


def _f(v) -> float:
    """转 float（兼容 Decimal）"""
    return float(v) if v is not None else 0.0


def calc_moving_average(closes: List, window: int) -> List[Optional[float]]:
    """计算简单移动平均线。

    :param closes: 收盘价序列
    :param window: 窗口期（如 5/20/60/250）
    :return: 与 closes 等长的列表，前 window-1 个为 None（数据不足）
    """
    n = len(closes)
    if n == 0:
        return []
    if window <= 0:
        return [None] * n

    arr = np.array([_f(c) for c in closes], dtype=float)
    result: List[Optional[float]] = []
    for i in range(n):
        if i < window - 1:
            result.append(None)
        else:
            result.append(float(arr[i - window + 1:i + 1].mean()))
    return result


def calc_bollinger_bands(closes: List, window: int = 20, num_std: float = 2.0):
    """布林带：中轨=MA(window)，上轨=中轨+num_std×标准差，下轨=中轨-num_std×标准差。

    标准差用总体标准差（ddof=0），与布林带惯例一致。
    :return: (upper, middle, lower) 三个与 closes 等长的列表，数据不足处为 None
    """
    n = len(closes)
    if n == 0:
        return [], [], []
    middle = calc_moving_average(closes, window)
    arr = np.array([_f(c) for c in closes], dtype=float)
    upper: List[Optional[float]] = []
    lower: List[Optional[float]] = []
    for i in range(n):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            seg = arr[i - window + 1:i + 1]
            std = float(seg.std())  # 总体标准差
            upper.append(middle[i] + num_std * std)
            lower.append(middle[i] - num_std * std)
    return upper, middle, lower


def calc_bollinger_signal(latest_close, upper, middle, lower, bandwidths):
    """布林带智能信号：识别价格相对布林带的位置、带宽形态，并给买卖概率推荐。

    概率采用连续计算：价格在布林带内的相对位置（下轨=0，上轨=1）线性映射到
    买入概率（下轨85 -> 上轨15），突破/跌破轨道时钳制。再按带宽分位分 5 档微调。

    :param latest_close: 最新收盘价
    :param upper/middle/lower: 最新日布林带三轨（None 表示数据不足）
    :param bandwidths: 区间内每日带宽序列 =(upper-lower)/middle×100，可含 None
    :return: {position, type, bandwidth_percentile, buy_prob, sell_prob, suggestion}
        position: above_upper/below_lower/near_upper/near_lower/middle/None
        type: warning(超买/压力) / success(超卖/支撑) / info(中性)
        buy_prob/sell_prob: 买入/卖出概率推荐（0-100，和为 100），数据不足时 None
    """
    if upper is None or middle is None or lower is None or _f(middle) == 0:
        return {'position': None, 'type': 'info', 'bandwidth_percentile': None,
                'buy_prob': None, 'sell_prob': None,
                'suggestion': '布林带数据不足（需20个交易日以上）'}

    price = _f(latest_close)
    up = _f(upper)
    mid = _f(middle)
    lo = _f(lower)
    bw_now = (up - lo) / mid * 100

    # 位置判断（用于文案与类型着色）
    if price > up:
        position, type_, base = 'above_upper', 'warning', f'价格突破布林上轨（{price:.2f} > {up:.2f}），短期超买'
    elif price < lo:
        position, type_, base = 'below_lower', 'success', f'价格跌破布林下轨（{price:.2f} < {lo:.2f}），短期超卖'
    elif price >= up * 0.98:
        position, type_, base = 'near_upper', 'warning', f'价格接近布林上轨压力位（{price:.2f}）'
    elif price <= lo * 1.02:
        position, type_, base = 'near_lower', 'success', f'价格接近布林下轨支撑位（{price:.2f}）'
    else:
        position, type_, base = 'middle', 'info', '价格运行于布林带中轨附近'

    # 连续基准概率：相对位置 pos（下轨=0，上轨=1），买入 = 85 - 70*pos
    # 突破上轨/跌破下轨时 pos 越界，钳制到 [0,1] -> 买入 15/85
    pos = (price - lo) / (up - lo) if up != lo else 0.5
    pos = max(0.0, min(1.0, pos))
    buy = 85 - 70 * pos

    # 带宽分位 + 5 档微调（分位越极端，对当前方向越确信或越蓄势）
    bws = [b for b in bandwidths if b is not None]
    pct = None
    bw_hint = ''
    if bws:
        arr = np.array(bws, dtype=float)
        pct = float((arr < bw_now).sum() / len(arr) * 100)
        if pct < 20:
            # 收窄蓄势：方向不明，拉回中性
            bw_hint = '；带宽收窄（处于区间低位），变盘在即'
            buy = 50.0
        elif pct < 40:
            # 偏窄：轻微确信当前方向 ±3
            bw_hint = '；带宽偏窄，趋势偏弱'
            buy += -3 if buy < 50 else 3
        elif pct < 60:
            bw_hint = ''  # 中性档，不偏移
        elif pct < 80:
            # 偏宽：较强确信 ±6
            bw_hint = '；带宽偏宽，趋势增强'
            buy += -6 if buy < 50 else 6
        else:
            # 放大：强趋势 ±10
            bw_hint = '；带宽放大（处于区间高位），波动加剧'
            buy += -10 if buy < 50 else 10

    # 钳制到 [5, 95] 并取整，留出极端但不归零的边界
    buy = int(round(max(5, min(95, buy))))
    sell = 100 - buy

    action = f'；推荐操作：买入推荐：{buy}%，卖出推荐：{sell}%'
    return {'position': position, 'type': type_,
            'bandwidth_percentile': pct, 'buy_prob': buy, 'sell_prob': sell,
            'suggestion': base + bw_hint + action}


def calc_volatility(change_pcts: List) -> Optional[float]:
    """年化波动率 = 日涨跌幅样本标准差 × √250。数据不足 2 个返回 None。"""
    if len(change_pcts) < 2:
        return None
    vals = [_f(c) for c in change_pcts]
    return statistics.stdev(vals) * math.sqrt(250)


def calc_annualized_return(start_close, end_close, days: int) -> Optional[float]:
    """几何年化收益率 = (end/start)^(250/days) - 1。days<=0 或 start<=0 返回 None。"""
    s = _f(start_close)
    if days <= 0 or s <= 0:
        return None
    e = _f(end_close)
    return (e / s) ** (250 / days) - 1


def calc_change_distribution(change_pcts: List, bin_size: float = 1.0) -> List[dict]:
    """涨跌幅分箱分布（直方图数据）。

    :return: [{label, min, max, count}]，按 bin 升序，左闭右开 [min, max)
    """
    if not change_pcts:
        return []
    vals = [_f(c) for c in change_pcts]
    lo, hi = min(vals), max(vals)
    start = math.floor(lo / bin_size) * bin_size
    end = math.ceil(hi / bin_size) * bin_size
    if end <= start:  # 所有值相同
        end = start + bin_size

    bins = []
    b = start
    while b < end - 1e-9:
        bins.append({'min': b, 'max': b + bin_size, 'count': 0})
        b += bin_size

    for v in vals:
        idx = int(math.floor((v - start) / bin_size))
        idx = max(0, min(idx, len(bins) - 1))
        bins[idx]['count'] += 1

    for b in bins:
        b['label'] = f"{b['min']:.0f}% ~ {b['max']:.0f}%"
    return bins


def calc_monthly_returns(dates: List[str], closes: List) -> List[dict]:
    """按月汇总收益率（月首收盘 -> 月末收盘）。

    :return: [{year, month, label:'YYYY-MM', return_rate}]，按月升序
    """
    if not dates:
        return []
    pairs = sorted(zip(dates, closes), key=lambda x: x[0])
    groups = {}  # (year, month) -> [first_close, last_close]
    order = []
    for d_str, close in pairs:
        d = datetime.strptime(d_str, '%Y-%m-%d').date()
        key = (d.year, d.month)
        if key not in groups:
            groups[key] = [_f(close), _f(close)]
            order.append(key)
        else:
            groups[key][1] = _f(close)

    result = []
    for key in order:
        y, m = key
        first, last = groups[key]
        rr = (last - first) / first if first else 0.0
        result.append({
            'year': y, 'month': m,
            'label': f"{y:04d}-{m:02d}",
            'return_rate': rr
        })
    return result


def calc_ma_signal(latest_close, ma60: Optional[float], ma250: Optional[float]) -> dict:
    """当前价相对均线位置信号，给出定投安全边际提示。

    :return: {ma60, ma60_diff_pct, ma250, ma250_diff_pct, suggestion}
    """
    latest = _f(latest_close)

    def diff(ma):
        if ma is None:
            return None
        ma = _f(ma)
        if ma == 0:
            return None
        return (latest - ma) / ma * 100

    ma60_diff = diff(ma60)
    ma250_diff = diff(ma250)

    if ma250_diff is not None and ma250_diff < 0:
        suggestion = f"当前价低于年线(MA250) {abs(ma250_diff):.2f}%，处于相对低位，定投安全边际较高"
    elif ma60_diff is not None and ma60_diff > 0:
        suggestion = f"当前价高于半年线(MA60) {ma60_diff:.2f}%，趋势偏强，注意追高风险"
    else:
        suggestion = "当前价处于均线中性区间，可按计划定投"

    return {
        'ma60': ma60, 'ma60_diff_pct': ma60_diff,
        'ma250': ma250, 'ma250_diff_pct': ma250_diff,
        'suggestion': suggestion
    }
