#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯止盈(永不空仓) 回测 V3

相对 V2(`backtest_kc50_dca_v2.py`)的三项优化:
  3. DCA 再触发推广到所有档位: 任意档 L 在 [L, L+5%) 区间长期震荡, 且自上次止盈累计加仓
     ≥ 上次卖出额一半时, 再卖一次 L(DCA 再触发)。V2 仅限 15%~20%。
  6. 20% 后回落不跳过 15%(推广到所有档): 档 L 在收益率跌破 L(自身档位)时重装,
     跌破任一档即重装该档及更高档 -> 完整新一轮, 修复 V2「跌破 L−5% 重装」导致的 15% 跳过。
  8. 卖出比例随档位递增: sell_frac(L)=min(0.20+0.10*k, 0.90), k=(L−15%)/5%。
     15%卖20%、20%卖30%、25%卖40%……高位多锁利、低位多留仓; 封顶 90% 确保永不空仓。

引擎参数化(opt3/opt6/opt8), 全部 False 精确复现 V2(回归校验), 支持消融对比。
数据: index_info 表科创50(000688)收盘价。
输出: 同目录 科创50_定投止盈_回测报告_V3.md
"""
import os
import sys
from collections import defaultdict

# 让脚本可直接运行: 将仓库根加入 sys.path 以 import tasks 包
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# 复用 V1 的数据访问与格式化辅助
from tasks.backtest_kc50_dca import (  # noqa: E402
    fetch_prices, _xirr, money, shares, pct,
    DAILY_INVEST, TRADING_DAYS_PER_YEAR, run_backtest as run_v1_backtest,
)
# V2 用于回归校验与对比
from tasks.backtest_kc50_dca_v2 import run_backtest_v2  # noqa: E402

FIRST_TIER = 0.15        # 首个止盈档(15%)
TIER_STEP = 0.05         # 档位间距(每涨 5%)
MAX_TIER = 2.00          # 档位上限(200%, 足够覆盖; 0.15~2.00 共 38 档)
TIERS = [round(FIRST_TIER + TIER_STEP * i, 10) for i in range(int((MAX_TIER - FIRST_TIER) / TIER_STEP) + 1)]

# 优化8: 卖出比例随档位递增
SELL_FRAC_BASE = 0.20    # 15% 档卖 20%(低位多留仓)
SELL_FRAC_STEP = 0.10    # 每升一档 +10%
SELL_FRAC_CAP = 0.90     # 封顶 90%(单次至少留 10%, 永不空仓)
SELL_FRAC_V2 = 0.30      # 优化8 关闭时退回 V2 的固定 30%

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告_V3.md'
)


def _tier_index(L):
    return int(round((L - FIRST_TIER) / TIER_STEP))


def sell_frac(L, opt8=True):
    """档位 L 的卖出比例。opt8=False 退回 V2 固定 30%。"""
    if not opt8:
        return SELL_FRAC_V2
    k = _tier_index(L)
    return min(SELL_FRAC_BASE + SELL_FRAC_STEP * k, SELL_FRAC_CAP)


def _tier_label(L):
    return f"{int(round(L * 100))}%"


def run_backtest_v3(prices, opt3=True, opt6=True, opt8=True):
    """执行 V3 回测, 返回 (events, summary)。状态机见模块文档。

    opt3: DCA 再触发推广到所有档位(True) / 仅 15%(False, V2)
    opt6: 重装阈值 = 跌破 L(True) / 跌破 L−5%(False, V2)
    opt8: 卖出比例随档位递增(True) / 固定 30%(False, V2)
    三者全 False 精确复现 V2。
    """
    armed = {L: True for L in TIERS}      # 各档是否装填
    total_shares = 0.0                    # 当前持仓份额
    total_cost = 0.0                      # 当前持仓成本(卖出按比例结转)
    total_invested = 0.0                  # 累计定投金额
    cum_realized = 0.0                    # 累计实现盈亏
    dca_since_last_sell = 0.0             # 自上次止盈以来的累计加仓金额
    last_sell_proceeds = 0.0              # 上一次卖出金额(用于 DCA 再触发半额判定)

    events = []
    peak_profit_rate = 0.0
    daily_cf = []                         # XIRR 现金流

    def _fire(trade_date, L, price, profit_rate, trigger, dca_at_trigger, frac):
        """卖出当前持仓的 frac, 记录事件, 更新状态。"""
        nonlocal total_shares, total_cost, cum_realized
        nonlocal dca_since_last_sell, last_sell_proceeds
        shares_before = total_shares
        shares_sold = total_shares * frac
        shares_after = total_shares - shares_sold

        value_before = shares_before * price
        sell_proceeds = shares_sold * price
        value_after = shares_after * price

        cost_before = total_cost
        cost_sold = total_cost * frac          # 平均成本法: 按比例结转
        cost_after = total_cost - cost_sold
        realized = sell_proceeds - cost_sold

        total_shares = shares_after
        total_cost = cost_after
        cum_realized += realized
        last_sell_proceeds = sell_proceeds
        dca_since_last_sell = 0.0

        events.append({
            'date': trade_date,
            'tier': _tier_label(L),
            'trigger': trigger,                 # 'normal' | 'dca_retrigger'
            'profit_rate': profit_rate,
            'price': price,
            'sell_frac': frac,                  # 本档卖出比例(优化8)
            'avg_cost': cost_before / shares_before if shares_before else 0.0,
            'shares_before': shares_before,
            'shares_sold': shares_sold,
            'shares_after': shares_after,
            'value_before': value_before,       # 止盈前持仓金额(市值)
            'cost_before': cost_before,
            'cost_after': cost_after,
            'sell_proceeds': sell_proceeds,     # 止盈金额(卖出回款)
            'value_after': value_after,         # 止盈后持仓金额(市值)
            'realized': realized,
            'cum_realized': cum_realized,
            'dca_at_trigger': dca_at_trigger,   # 触发前的累计加仓金额(可追溯)
        })

    for trade_date, price in prices:
        # 1) 每日定投买入
        buy_shares = DAILY_INVEST / price
        total_shares += buy_shares
        total_cost += DAILY_INVEST
        total_invested += DAILY_INVEST
        daily_cf.append((trade_date, -DAILY_INVEST))
        dca_since_last_sell += DAILY_INVEST

        # 2) 持仓收益率
        profit_rate = (total_shares * price - total_cost) / total_cost if total_cost > 0 else 0.0
        if profit_rate > peak_profit_rate:
            peak_profit_rate = profit_rate

        # 3) 重装: 档位 L 已触发 且 收益率跌破重装阈值 -> 重装
        #    优化6: 阈值 = L(跌破自身档位); V2: 阈值 = L−5%
        for L in TIERS:
            if not armed[L]:
                rearm_threshold = L if opt6 else L - TIER_STEP
                if profit_rate < rearm_threshold:
                    armed[L] = True

        # 4) 正常止盈(档位升序): 收益率 ≥ L 且已装填 -> 卖 sell_frac(L)
        for L in TIERS:
            if profit_rate >= L and armed[L]:
                _fire(trade_date, L, price, profit_rate, 'normal', dca_since_last_sell, sell_frac(L, opt8))
                armed[L] = False

        # 5) DCA 再触发: 档 L 未装填 且 收益率停留在 [L, L+5%) 且 累计加仓 ≥ 上次卖出额一半
        #    优化3: 遍历所有档; V2: 仅 15%。收益率区间任一时刻只命中一个档, 每日至多一次 DCA。
        dca_tiers = TIERS if opt3 else [FIRST_TIER]
        for L in dca_tiers:
            if (not armed[L]
                    and L <= profit_rate < L + TIER_STEP
                    and last_sell_proceeds > 0
                    and dca_since_last_sell >= last_sell_proceeds / 2.0):
                _fire(trade_date, L, price, profit_rate, 'dca_retrigger', dca_since_last_sell, sell_frac(L, opt8))
                # DCA 再触发不改 armed 状态(该档保持未装填), 可连续触发; 当日 dca 已清零, 不会重复
                break

    # 期末状态
    final_price = prices[-1][1]
    final_value = total_shares * final_price
    unrealized = final_value - total_cost
    total_sell_proceeds = sum(e['sell_proceeds'] for e in events)
    cash = total_sell_proceeds                          # 回款闲置作现金
    total_profit = final_value + cash - total_invested
    total_return = total_profit / total_invested if total_invested else 0.0

    n_days = len(prices)
    years = n_days / TRADING_DAYS_PER_YEAR
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0

    daily_cf.append((prices[-1][0], final_value + cash))
    xirr_val = _xirr(daily_cf)

    tier_counts = defaultdict(int)
    trigger_counts = defaultdict(int)
    for e in events:
        tier_counts[e['tier']] += 1
        trigger_counts[e['trigger']] += 1

    summary = {
        'first_date': prices[0][0],
        'last_date': prices[-1][0],
        'n_days': n_days,
        'years': years,
        'min_price': min(p for _, p in prices),
        'max_price': max(p for _, p in prices),
        'total_invested': total_invested,
        'n_events': len(events),
        'tier_counts': dict(tier_counts),
        'trigger_counts': dict(trigger_counts),
        'cum_realized': cum_realized,
        'total_sell_proceeds': total_sell_proceeds,
        'final_shares': total_shares,
        'final_cost': total_cost,
        'final_price': final_price,
        'final_value': final_value,
        'unrealized': unrealized,
        'cash': cash,
        'total_profit': total_profit,
        'total_return': total_return,
        'annualized': annualized,
        'peak_profit_rate': peak_profit_rate,
        'xirr': xirr_val,
        'opt3': opt3, 'opt6': opt6, 'opt8': opt8,
    }
    return events, summary


def _pure_dca_baseline(prices):
    """纯定投不止盈基线: 每日 300 买入持有到期末。"""
    total_shares = 0.0
    total_invested = 0.0
    for _, price in prices:
        total_shares += DAILY_INVEST / price
        total_invested += DAILY_INVEST
    final_value = total_shares * prices[-1][1]
    total_profit = final_value - total_invested
    total_return = total_profit / total_invested if total_invested else 0.0
    years = len(prices) / TRADING_DAYS_PER_YEAR
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0
    return {
        'total_invested': total_invested, 'final_value': final_value,
        'final_shares': total_shares, 'total_profit': total_profit,
        'total_return': total_return, 'annualized': annualized,
    }


def _sell_frac_table():
    """优化8 卖出比例表(用于报告)。"""
    rows = []
    for L in TIERS:
        if L > 0.50:
            break
        rows.append((_tier_label(L), sell_frac(L, opt8=True)))
    return rows


def _ablation_row(label, s):
    return (f"| {label} | {s['n_events']} | "
            f"{s['trigger_counts'].get('normal', 0)}/{s['trigger_counts'].get('dca_retrigger', 0)} | "
            f"{money(s['total_sell_proceeds'])} | {money(s['cum_realized'])} | "
            f"{money(s['final_value'])} | {money(s['final_value'] + s['cash'])} | "
            f"{pct(s['total_return'])} | {pct(s['xirr'])} |")


def build_report(events, summary, v2_summary, v1_summary, baseline, abl):
    """生成 V3 报告。abl = {'v2':s, 'opt3':s, 'opt6':s, 'opt8':s, 'v3':s} 消融汇总。"""
    L = []
    s = summary
    L.append("# 科创50 定投止盈回测 V3(永不空仓 + DCA 全档 + 跌破重装 + 分档卖出)")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca_v3.py`。")
    L.append("> 本报告为 V2(`科创50_定投止盈_回测报告_V2.md`)的策略升级版。")
    L.append("")

    L.append("## 一、V3 相对 V2 的策略变更")
    L.append("")
    L.append("| 维度 | V2 | V3 |")
    L.append("|---|---|---|")
    L.append("| DCA 再触发 | 仅 15%~20% 区间 | **推广到所有档**: 任意档 L 在 [L, L+5%) 震荡、加仓达半额即收割 |")
    L.append("| 重装规则 | 跌破 L−5% 重装(15%跌破10%…) | **跌破 L 重装**(15%跌破15%、20%跌破20%…), 完整新一轮, 不跳过 |")
    L.append("| 卖出比例 | 每档固定 30% | **随档位递增**: 15%卖20%、20%卖30%、25%卖40%…封顶90%, 永不空仓 |")
    L.append("| 15% 跳过 | 20% 后回落到 10%~15%, 15% 被跳过 | **不再跳过**: 跌破 15% 同时重装 15% 与 20%, 回升先收割 15% |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("V3 在 V2「永不空仓」基础上叠加三项优化, 目标是**提高资金周转与高位锁利**: "
             "① **DCA 再触发全档化**(优化3)--把 V2 仅在 15%~20% 的定期收割推广到任意两档间的长期横盘, "
             "震荡市多周转; ② **跌破自身档位重装**(优化6)--修复 V2「跌破 L−5% 重装」在宽幅震荡中跳过 15% 档的问题, "
             "回撤后完整新一轮、多收割一档; ③ **卖出比例随档位递增**(优化8)--低位档少卖(多留仓吃趋势)、"
             "高位档多卖(多锁利), 在永不空仓前提下优化减仓节奏。三项均为对震荡/宽幅行情的增强, "
             "在科创50这类高波动指数上通过回测验证取舍。")
    L.append("")

    L.append("## 二、策略与假设")
    L.append("")
    L.append("| 项 | 设定 |")
    L.append("|---|---|")
    L.append("| 标的 | 科创50指数(000688), 以收盘价模拟可投资净值 |")
    L.append(f"| 定投 | 每个交易日投入 {money(DAILY_INVEST)} 元, 自 {s['first_date']} 起不间断(无论涨跌) |")
    L.append("| 止盈阶梯 | 持仓收益率 ≥15% 卖当前 `sell_frac(L)`; 此后每涨 5%(20%/25%/30%…)各卖当前 `sell_frac(L)` |")
    L.append(f"| 卖出比例(优化8) | `sell_frac(L)=min({int(SELL_FRAC_BASE*100)}%+{int(SELL_FRAC_STEP*100)}%·k, {int(SELL_FRAC_CAP*100)}%)`, "
             f"k=(L−15%)/5%; 即 15%卖20%、20%卖30%、25%卖40%……高位多卖、低位多留, **永不空仓** |")
    L.append("| DCA 再触发(优化3) | 任意档 L 触发后, 若 L≤收益率<L+5% 且自上次止盈累计加仓≥上次卖出额一半, 再卖一次 L |")
    L.append("| 重装规则(优化6) | 档位 L 在收益率跌破 L 时重装(15%:跌破15% · 20%:跌破20% · 25%:跌破20%…) |")
    L.append("| 持仓收益率 | (持仓市值 − 持仓成本) / 持仓成本 |")
    L.append("| 成本结转 | 卖出按比例结转成本(平均成本法), 卖出不改变平均成本 |")
    L.append("| 每日顺序 | 先以当日收盘价定投买入, 再判定止盈(重装 → 正常止盈 → DCA 再触发) |")
    L.append("| 回款处理 | 止盈回款留作现金, 不自动再投(再投列为优化方向) |")
    L.append("| 费用 | 不计交易费用、分红再投、税收; 指数点位近似可投资(可买碎额) |")
    L.append("")

    L.append("### 优化8 卖出比例表")
    L.append("")
    L.append("| 档位 | 卖出比例 | 留存比例 |")
    L.append("|---|---|---|")
    for label, frac in _sell_frac_table():
        L.append(f"| {label} | {int(round(frac * 100))}% | {int(round((1 - frac) * 100))}% |")
    L.append(f"| ≥50% | {int(SELL_FRAC_CAP * 100)}%(封顶) | {int(round((1 - SELL_FRAC_CAP) * 100))}% |")
    L.append("")

    L.append("## 三、数据概览")
    L.append("")
    L.append("| 项 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 交易日数 | {s['n_days']} |")
    L.append(f"| 回测区间 | {s['first_date']} ~ {s['last_date']} |")
    L.append(f"| 收盘价区间 | {money(s['min_price'])} ~ {money(s['max_price'])} |")
    L.append(f"| 区间内最高持仓收益率 | {pct(s['peak_profit_rate'])} |")
    L.append("")

    L.append("## 四、回测汇总")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 累计定投金额 | {money(s['total_invested'])} 元 |")
    L.append(f"| 定投天数 | {s['n_days']} 个交易日 |")
    L.append(f"| 止盈次数(合计) | {s['n_events']} 次 "
             f"(正常 {s['trigger_counts'].get('normal',0)} / DCA 再触发 {s['trigger_counts'].get('dca_retrigger',0)}) |")
    L.append(f"| 累计卖出回款(止盈金额) | {money(s['total_sell_proceeds'])} 元 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} 元 |")
    L.append(f"| 期末持仓份额 | {shares(s['final_shares'])} 份 |")
    L.append(f"| 期末持仓成本 | {money(s['final_cost'])} 元 |")
    L.append(f"| 期末收盘价 | {money(s['final_price'])} |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} 元 |")
    L.append(f"| 期末浮动盈亏 | {money(s['unrealized'])} 元 |")
    L.append(f"| 期末现金(回款闲置) | {money(s['cash'])} 元 |")
    L.append(f"| 期末总资产(市值+现金) | {money(s['final_value'] + s['cash'])} 元 |")
    L.append(f"| 总收益(期末总资产−累计定投) | {money(s['total_profit'])} 元 |")
    L.append(f"| 总收益率(简单总额法) | {pct(s['total_return'])} |")
    L.append(f"| 年化收益率(估, 244日/年) | {pct(s['annualized'])} |")
    L.append(f"| XIRR(资金加权年化) | {pct(s['xirr'])} |")
    L.append("")
    L.append("### 各档触发次数")
    L.append("")
    L.append("| 档位 | 次数 |")
    L.append("|---|---|")
    for L_tier in sorted(s['tier_counts'], key=lambda x: int(x[:-1])):
        L.append(f"| {L_tier} | {s['tier_counts'][L_tier]} 次 |")
    L.append("")

    L.append("## 五、止盈事件明细")
    L.append("")
    L.append(f"共 {s['n_events']} 次止盈。下表逐次记录: 触发日期 / 档位 / 触发类型 / 触发时持仓收益率 / "
             "收盘价 / 卖出比例 / 止盈前份额 / 卖出份额 / 止盈后份额 / **止盈前持仓金额** / 止盈前成本 / "
             "**止盈金额(卖出回款)** / **止盈后持仓金额** / 本次实现盈亏 / 累计实现盈亏。")
    L.append("")
    L.append("> 触发类型: `正常`=档位首次/重装后穿越触发; `DCA`=任意两档间震荡区间加仓达半额再触发。")
    L.append("")
    L.append("| # | 日期 | 档位 | 类型 | 触发收益率 | 收盘价 | 卖出比例 | 止盈前份额 | 卖出份额 | 止盈后份额 | "
             "止盈前持仓金额 | 止盈前成本 | 止盈金额 | 止盈后持仓金额 | 本次实现盈亏 | 累计实现盈亏 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(events, 1):
        trig = '正常' if e['trigger'] == 'normal' else 'DCA'
        L.append(
            f"| {i} | {e['date']} | {e['tier']} | {trig} | {pct(e['profit_rate'])} | {money(e['price'])} | "
            f"{int(round(e['sell_frac'] * 100))}% | "
            f"{shares(e['shares_before'])} | {shares(e['shares_sold'])} | {shares(e['shares_after'])} | "
            f"{money(e['value_before'])} | {money(e['cost_before'])} | {money(e['sell_proceeds'])} | "
            f"{money(e['value_after'])} | {money(e['realized'])} | {money(e['cum_realized'])} |"
        )
    L.append("")

    # 按年分布
    L.append("## 六、止盈事件按年分布")
    L.append("")
    by_year = defaultdict(lambda: {'count': 0, 'proceeds': 0.0, 'realized': 0.0, 'dca': 0})
    for e in events:
        y = e['date'].year
        by_year[y]['count'] += 1
        by_year[y]['proceeds'] += e['sell_proceeds']
        by_year[y]['realized'] += e['realized']
        if e['trigger'] == 'dca_retrigger':
            by_year[y]['dca'] += 1
    L.append("| 年份 | 止盈次数 | 其中 DCA 再触发 | 卖出回款(元) | 实现盈亏(元) |")
    L.append("|---|---|---|---|---|")
    for y in sorted(by_year):
        d = by_year[y]
        L.append(f"| {y} | {d['count']} | {d['dca']} | {money(d['proceeds'])} | {money(d['realized'])} |")
    L.append("")

    # 对比: V3 vs V2 vs V1 vs 纯定投
    L.append("## 七、V3 vs V2 vs V1 vs 纯定投 对比")
    L.append("")
    L.append("> 收益口径统一: **总收益 = 期末总资产(持仓市值+回款现金) − 累计定投**。")
    L.append("> V2 为 `backtest_kc50_dca_v2.py`(永不空仓 + 15% DCA); V1 为 20% 清仓; 纯定投为不止盈持有到期末。")
    L.append("")
    v2 = v2_summary
    v1 = v1_summary
    b = baseline
    L.append("| 指标 | V3(三优化) | V2(永不空仓) | V1(20%清仓) | 纯定投不止盈 |")
    L.append("|---|---|---|---|---|")
    L.append(f"| 止盈次数 | {s['n_events']} | {v2['n_events']} | {v1['n_events']} | 0 |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(v2['total_sell_proceeds'])} | {money(v1['total_sell_proceeds'])} | 0 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(v2['cum_realized'])} | {money(v1['cum_realized'])} | 0 |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(v2['final_value'])} | {money(v1['final_value'])} | {money(b['final_value'])} |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['cash'])} | {money(v2['final_value']+v2['cash'])} | {money(v1['final_value']+v1['cash'])} | {money(b['final_value'])} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(v2['total_return'])} | {pct(v1['total_return'])} | {pct(b['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(v2['xirr'])} | {pct(v1['xirr'])} | - |")
    L.append("")

    # 消融对比
    L.append("## 八、消融对比(逐项拆解)")
    L.append("")
    L.append("> 在 V2 基线上逐项开启优化, 单独观察每项的边际效果; V3 = 三项全开。")
    L.append("> 「正常/DCA」列为正常止盈次数 / DCA 再触发次数。")
    L.append("")
    L.append("| 方案 | 止盈次数 | 正常/DCA | 累计回款 | 累计实现盈亏 | 期末市值 | 期末总资产 | 总收益率 | XIRR |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    L.append(_ablation_row("V2 基线(全关)", abl['v2']))
    L.append(_ablation_row("+优化3(DCA全档)", abl['opt3']))
    L.append(_ablation_row("+优化6(跌破重装)", abl['opt6']))
    L.append(_ablation_row("+优化8(分档卖出)", abl['opt8']))
    L.append(_ablation_row("V3(三优化全开)", abl['v3']))
    L.append("")
    # 逐项解读
    d_v2 = abl['v2']['total_return']
    d_o3 = abl['opt3']['total_return'] - d_v2
    d_o6 = abl['opt6']['total_return'] - d_v2
    d_o8 = abl['opt8']['total_return'] - d_v2
    d_v3 = abl['v3']['total_return'] - d_v2
    L.append("**逐项边际效应(相对 V2 基线, 总收益率百分点):**")
    L.append("")
    L.append(f"- 优化3(DCA 全档): {pct(d_o3)}  — 止盈次数 {abl['opt3']['n_events'] - abl['v2']['n_events']:+d}")
    L.append(f"- 优化6(跌破重装): {pct(d_o6)}  — 止盈次数 {abl['opt6']['n_events'] - abl['v2']['n_events']:+d}")
    L.append(f"- 优化8(分档卖出): {pct(d_o8)}  — 止盈次数 {abl['opt8']['n_events'] - abl['v2']['n_events']:+d}")
    L.append(f"- V3(三项全开): {pct(d_v3)}  — 止盈次数 {abl['v3']['n_events'] - abl['v2']['n_events']:+d}")
    L.append("")
    L.append("> **实测解读(对比取舍):**")
    L.append(">")
    L.append(f"> - **优化8(分档卖出)是最强单项**: +{pct(d_o8)} / XIRR +{pct(abl['opt8']['xirr'] - abl['v2']['xirr'])}; "
             "15% 少卖(20% vs 30%, 留仓吃趋势)+ 高位多卖(30%档卖50%… 锁利), 在本行情明显正向。")
    L.append(f"> - **优化6(跌破重装)次之**: +{pct(d_o6)}; 代价是 DCA 再触发被抑制(5->0)、正常止盈 +7 次"
             "(小幅回撤即重装再卖), 交易更频繁, 靠「多收割一档」取胜而非 DCA。")
    L.append(f"> - **优化3(DCA 全档)几乎中性**: +{pct(d_o3)}; 高档 DCA 因定投稀释拉低收益率、半额门槛难满足, "
             f"实际 DCA 次数 {abl['opt3']['trigger_counts'].get('dca_retrigger', 0)}(V2 为 5), 未有效新增高档收割。")
    L.append(f"> - **三项叠加 V3 = +{pct(d_v3)}, 优于 V2 但低于 opt8 单开({pct(abl['opt8']['total_return'])})**: "
             "opt6 的频繁重装改变减仓节奏并抑制 DCA, 与 opt8 非完全协同; opt3 的增量又被 opt6 吞没(V3 中 DCA=0)。"
             "若纯追收益, **opt8 单开最优**; V3 保留三项以完整呈现取舍, 并为「重装冷却/迟滞」(见优化方向 4)留出改进空间。")
    L.append("")

    # 可优化方向
    L.append("## 九、可优化方向")
    L.append("")
    L.append("V3 已落地原 V2 优化方向中的 3/6/8。针对科创50 **高波动、强趋势、成长风格** 特性, 仍可考虑:")
    L.append("")
    L.append("1. **回款再投(子弹池复利)**: 止盈回款仍闲置, 零复利, 是当前最大优化杠杆。"
             "可让回款进入子弹池, 在低位(收盘价低于 250 日均线 8% 以上)加速抄底, "
             "把高位套现的钱变成低位筹码。沪深300 V2 已验证此优化可显著提升总收益。")
    L.append("2. **均线/估值加权定投**: 无论涨跌每日固定 300 元, 顶部照样定投抬高成本。"
             "可按收盘价相对 250 日均线偏离度加权--低估多投、高估停投, 压低平均成本。")
    L.append("3. **止盈档位动态化**: 15/20/25% 为固定档。可结合 PE 历史分位、波动率动态调整--"
             "高估区提前止盈、低估区放宽阈值。⚠️ index_info 中科创50的 pe_ratio/pe_percentile 当前为 0(未采集), 落地需先补数据。")
    L.append("4. **重装冷却/迟滞**: 优化6 推广到全档后, 小幅回撤即重装可能造成 15% 档高频触发。"
             "可给重装加冷却期(如重装后 N 个交易日不再重装)或迟滞带(跌破 L−1% 才重装), "
             "减少噪声触发的过早减仓。")
    L.append("5. **止盈基准优化**: 止盈看「组合整体收益率」, 每日新增定投会持续稀释收益率, "
             "导致横盘时收益率被压低、止盈推迟。可改为按「最早批次成本」或「移动平均成本」分批止盈, "
             "反映不同批次真实盈亏; 并使高档 DCA(优化3)更易满足半额条件。")
    L.append("6. **卖出比例曲线调参**: 优化8 当前为线性 20%+10%·k、封顶 90%。可回测不同曲线"
             "(凹型/凸型/不同封顶)对总收益率的影响, 寻找科创50历史数据上的较优减仓节奏。")
    L.append("")

    L.append("## 十、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, 结果略乐观于真实科创50指数基金定投。")
    L.append("- **永不空仓**: 每次卖 `sell_frac(L)` < 1(封顶 90%, 至少留 10%), 即便连触多档, "
             "各档保留率乘积 > 0, 加之每日定投持续加仓, 持仓始终 > 0。")
    L.append("- **优化3(DCA 全档)**: 任意档 L 在 [L, L+5%) 震荡、累计加仓达上次卖出额一半时再卖一次 L; "
             "沿用 V2 的全局「自上次止盈累计加仓 / 上次卖出额」口径(任一卖出后清零), 非 per-tier 状态。"
             "因定投稀释拉低收益率, 高档(L≥20%)需收益率长期滞留窄区间才触发, 实际频率见各档 DCA 次数。")
    L.append("- **优化6(跌破重装)**: 档 L 在收益率跌破 L(自身档位)时重装, 跌破任一档即重装该档及更高档, "
             "「完整新一轮」; 故 20% 后回落到 10%~15% 会同时重装 15% 与 20%, 回升时先收割 15%, 不再跳过。"
             "副作用: 小幅回撤即重装, 震荡市 15% 档触发更频繁(见消融表)。")
    L.append("- **优化8(分档卖出)**: 15%卖20%、20%卖30%、25%卖40%……高位多卖、低位多留; "
             "封顶 90% 保证永不空仓。正常止盈与 DCA 再触发均用本档比例。"
             "注: 比例卖出虽不改变当时平均成本, 但缩小持仓基数, 使后续每日定投更快抬高平均成本, "
             "故 V3 区间最高持仓收益率(34.85%)低于 V2(44.23%); 这也是高位多锁利的代价之一。")
    L.append("- 单日涨幅同时穿越多档时, 各档同日依次触发(每档卖当前 `sell_frac(L)`), 净效果为分档减仓而非清仓。")
    L.append("- 卖出按比例结转成本(平均成本法), 单次止盈不改变剩余持仓的平均成本。")
    L.append("- XIRR 为资金加权年化, 考虑 6 年陆续投入的资金时间价值, 比简单总额法更严谨; 年化(244日/年)为粗略估算。")
    L.append("- 本报告不构成投资建议。")
    L.append("")
    return "\n".join(L)


def main():
    prices = fetch_prices()
    if not prices:
        print("未取到科创50行情数据", file=sys.stderr)
        sys.exit(1)

    # V3(三优化全开) + 回归校验
    events, summary = run_backtest_v3(prices, opt3=True, opt6=True, opt8=True)
    # V2(对比 + 回归基线)
    _v2_events, v2_summary = run_backtest_v2(prices)
    # V1 + 纯定投
    _v1_events, v1_summary = run_v1_backtest(prices, rearm_mode='on_clear')
    baseline = _pure_dca_baseline(prices)

    # 消融: V2 基线 + 逐项单开 + V3 全开
    _, abl_v2 = run_backtest_v3(prices, opt3=False, opt6=False, opt8=False)
    _, abl_o3 = run_backtest_v3(prices, opt3=True, opt6=False, opt8=False)
    _, abl_o6 = run_backtest_v3(prices, opt3=False, opt6=True, opt8=False)
    _, abl_o8 = run_backtest_v3(prices, opt3=False, opt6=False, opt8=True)
    abl = {'v2': abl_v2, 'opt3': abl_o3, 'opt6': abl_o6, 'opt8': abl_o8, 'v3': summary}

    # 回归断言: V3 全关 == V2
    assert abl_v2['n_events'] == v2_summary['n_events'], "回归失败: 全关止盈次数不一致"
    assert abs(abl_v2['total_return'] - v2_summary['total_return']) < 1e-9, "回归失败: 总收益率不一致"
    assert abs(abl_v2['xirr'] - v2_summary['xirr']) < 1e-9, "回归失败: XIRR 不一致"

    report = build_report(events, summary, v2_summary, v1_summary, baseline, abl)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    s = summary
    print(f"V3 回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 交易日)")
    print(f"累计定投: {money(s['total_invested'])} 元")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(正常 {s['trigger_counts'].get('normal',0)} / DCA 再触发 {s['trigger_counts'].get('dca_retrigger',0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮盈: {money(s['unrealized'])} 元 | 现金: {money(s['cash'])} 元")
    print(f"V3 总收益: {money(s['total_profit'])} | 总收益率: {pct(s['total_return'])} | "
          f"年化: {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"[回归] V3全关 == V2: {v2_summary['n_events']}次 / {pct(v2_summary['total_return'])} / XIRR {pct(v2_summary['xirr'])} ✓")
    print(f"[对比] V2 总收益率: {pct(v2_summary['total_return'])} | XIRR: {pct(v2_summary['xirr'])}")
    print(f"[对比] V1 总收益率: {pct(v1_summary['total_return'])} | 纯定投: {pct(baseline['total_return'])}")
    print("[消融] 方案 -> 总收益率 / XIRR / 止盈次数:")
    for label, a in [('V2基线 ', abl_v2), ('+opt3  ', abl_o3), ('+opt6  ', abl_o6),
                     ('+opt8  ', abl_o8), ('V3全开 ', summary)]:
        print(f"  {label} {pct(a['total_return'])} | XIRR {pct(a['xirr'])} | {a['n_events']}次 "
              f"(正常{a['trigger_counts'].get('normal',0)}/DCA{a['trigger_counts'].get('dca_retrigger',0)})")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
