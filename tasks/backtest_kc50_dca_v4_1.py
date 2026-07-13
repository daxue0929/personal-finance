#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯递增止盈(去掉 10% 档) 回测 V4

相对 V3(`backtest_kc50_dca_v3.py`)的策略变更:
  - **去掉 10% 档**: 首档改为 15%, 共 8 档(15%/20%/25%/30%/35%/40%/45%/50%)。
    其余规则同 V3: 卖比 = 2×档位、重装 L−2.5%、全档 DCA 再触发(15%~45%)、50% 清仓。

动机: V3 报告核心发现指出「10% 档过早过频削薄底仓(本回测触发 17 次)」是 V3 总收益率
(18.84%)弱于 V2(24.32%)的主因之一--10%~15% 的小涨就卖出 20% 底仓, 抬高机会成本。
V4 去掉 10% 档, 让底仓在 10%~15% 区间不被削薄, 验证收益能否回升、是否接近或超过 V2。

引擎复用 V3 的 `V3Engine`(已参数化), 仅传入 V4 档位配置。

数据: index_info 表科创50(000688)收盘价。
输出: 同目录 科创50_定投止盈_回测报告_V4.md
"""
import os
import sys
from collections import defaultdict

# 让脚本可直接运行: 将仓库根加入 sys.path 以 import tasks 包
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# 复用 V1 的数据访问与格式化辅助, 及 V3 的参数化引擎
from tasks.backtest_kc50_dca import (  # noqa: E402
    fetch_prices, _xirr, money, shares, pct,
    DAILY_INVEST, TRADING_DAYS_PER_YEAR, run_backtest as run_v1_backtest,
)
from tasks.backtest_kc50_dca_v2 import run_backtest_v2  # noqa: E402  (V4 vs V2 同区间对比)
from tasks.backtest_kc50_dca_v3_1 import V3Engine, run_backtest_v3, _tier_label  # noqa: E402

FIRST_TIER = 0.15         # 首个止盈档(15%, 去掉 V3 的 10% 档)
TIER_STEP = 0.05          # 档位间距(每涨 5%)
LAST_TIER = 0.50          # 封顶档(50% 清仓)
REARM_OFFSET = 0.025      # 重装阈值: 跌破 L−2.5% 重装(同 V3)

# 8 个止盈档: 15%/20%/25%/30%/35%/40%/45%/50%(去掉 V3 的 10% 档)
TIERS = [round(FIRST_TIER + TIER_STEP * i, 10)
         for i in range(int(round((LAST_TIER - FIRST_TIER) / TIER_STEP)) + 1)]

# 各档卖出比例 = 2×档位(15%->30%, 20%->40%, …, 50%->100%)
TIER_SELL_FRAC = {L: round(2.0 * L, 10) for L in TIERS}

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告_V4.md'
)


def run_backtest_v4(prices):
    """执行 V4 回测, 返回 (events, summary)。复用 V3Engine, 传入 V4 档位配置。"""
    eng = V3Engine(tiers=TIERS, tier_sell_frac=TIER_SELL_FRAC,
                   rearm_offset=REARM_OFFSET, tier_step=TIER_STEP, daily_invest=DAILY_INVEST)
    for trade_date, price in prices:
        eng.step(trade_date, price)

    events = eng.events
    total_shares = eng.total_shares
    total_cost = eng.total_cost
    total_invested = eng.total_invested
    cum_realized = eng.cum_realized
    daily_cf = eng.daily_cf
    peak_profit_rate = eng.peak_profit_rate

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


def build_report(events, summary, v3_summary, v2_summary, v1_summary, baseline):
    L = []
    s = summary
    L.append("# 科创50 定投止盈回测 V4(去掉 10% 档 + 递增卖比 + 50% 清仓)")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca_v4.py`(复用 V3 参数化引擎 `V3Engine`)。")
    L.append("> 本报告为 V3(`科创50_定投止盈_回测报告_V3.md`)的变体: 去掉 10% 档。")
    L.append("> 对比口径: V4/V3/V2/V1/纯定投均用**同一数据区间**(本报告数据日)重跑, 公平对比。")
    L.append("")

    L.append("## 一、V4 相对 V3 的策略变更")
    L.append("")
    L.append("| 维度 | V3(10% 起 9 档) | V4(15% 起 8 档) |")
    L.append("|---|---|---|")
    L.append("| 止盈档位 | 10/15/20/25/30/35/40/45/50% 共 9 档 | **去掉 10% 档**, 15/20/25/30/35/40/45/50% 共 8 档 |")
    L.append("| 首档卖出 | 10% 卖 20% | **15% 卖 30%**(10%~15% 区间不再卖出) |")
    L.append("| 卖出比例 | 卖比 = 2×档位(同) | 卖比 = 2×档位(**不变**) |")
    L.append("| 重装阈值 | L−2.5%(同) | L−2.5%(**不变**) |")
    L.append("| DCA 再触发 | 10%~45% 共 8 档 | **15%~45% 共 7 档**(去掉 10% 档的 DCA) |")
    L.append("| 50% 清仓 | 50% 卖 100%(同) | 50% 卖 100%(**不变**) |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("V3 报告核心发现指出: V3 总收益率(18.84%)弱于 V2(24.32%)的**主因之一是 10% 档过早、"
             "过频削薄底仓**--本回测 10% 档触发 17 次, 在仅 10%~15% 的小涨中就卖出 20% 底仓, "
             "而 V2 从 15% 起卖、底仓更厚。V4 去掉 10% 档, 让持仓在 10%~15% 区间不被削薄, "
             "15% 首次触发时持仓更大、锁利基数更高, 验证「去掉过早止盈档」能否让收益回升、"
             "接近甚至超过 V2。其余规则(递增卖比、L−2.5% 重装、全档 DCA、50% 清仓)均与 V3 一致, "
             "以隔离「10% 档」这一单一变量。")
    L.append("")

    L.append("## 二、策略与假设")
    L.append("")
    L.append("| 项 | 设定 |")
    L.append("|---|---|")
    L.append("| 标的 | 科创50指数(000688), 以收盘价模拟可投资净值 |")
    L.append(f"| 定投 | 每个交易日投入 {money(DAILY_INVEST)} 元, 自 {s['first_date']} 起不间断(无论涨跌) |")
    L.append("| 止盈档位 | 持仓收益率 ≥15%/20%/25%/30%/35%/40%/45%/50% 共 8 档, 每涨 5% 一档(**无 10% 档**) |")
    L.append("| 卖出比例 | **卖比 = 2×档位**: 15%卖30%、20%卖40%、25%卖50%、30%卖60%、"
             "35%卖70%、40%卖80%、45%卖90%、**50%卖100%(清仓)** |")
    L.append("| DCA 再触发 | 档 L 触发后, 若 L≤收益率<L+5% 且「该档自上次减仓累计定投 ≥ 该档上次卖出额一半」, "
             "再卖一次该档(卖比仍 = 2L); 适用于 15%~45% 共 7 档, 各档独立追踪 |")
    L.append("| 重装规则 | 档位 L 在收益率跌破 **L−2.5%** 时重装(15%:跌破12.5% · 20%:跌破17.5% · … · 50%:跌破47.5%) |")
    L.append("| 50% 清仓 | 50% 档卖 100%, 持仓归零; 之后每日定投重新积累, 收益率跌回近 0 触发全档重装 |")
    L.append("| 持仓收益率 | (持仓市值 − 持仓成本) / 持仓成本 |")
    L.append("| 成本结转 | 卖出按比例结转成本(平均成本法), 卖出不改变平均成本 |")
    L.append("| 每日顺序 | 先以当日收盘价定投买入, 再判定止盈 |")
    L.append("| 回款处理 | 止盈回款留作现金, 不自动再投(再投列为优化方向) |")
    L.append("| 费用 | 不计交易费用、分红再投、税收; 指数点位近似可投资(可买碎额) |")
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
    # 各档触发次数(列全部 8 档, 含 0 次)
    L.append("### 各档触发次数")
    L.append("")
    L.append("| 档位 | 卖出比例 | 次数 |")
    L.append("|---|---|---|")
    for L_val in TIERS:
        L_tier = _tier_label(L_val)
        cnt = s['tier_counts'].get(L_tier, 0)
        L.append(f"| {L_tier} | 卖{int(TIER_SELL_FRAC[L_val]*100)}% | {cnt} 次 |")
    L.append("")

    L.append("## 五、止盈事件明细")
    L.append("")
    L.append(f"共 {s['n_events']} 次止盈。下表逐次记录: 触发日期 / 档位 / 触发类型 / 触发时持仓收益率 / "
             "收盘价 / 止盈前份额 / 卖出份额 / 止盈后份额 / **止盈前持仓金额** / 止盈前成本 / "
             "**止盈金额(卖出回款)** / **止盈后持仓金额** / 本次实现盈亏 / 累计实现盈亏。")
    L.append("")
    L.append("> 触发类型: `正常`=档位首次/重装后穿越触发; `DCA`=该档 [L, L+5%) 震荡区间加仓达半额再触发。")
    L.append("")
    L.append("| # | 日期 | 档位 | 类型 | 触发收益率 | 收盘价 | 止盈前份额 | 卖出份额 | 止盈后份额 | "
             "止盈前持仓金额 | 止盈前成本 | 止盈金额 | 止盈后持仓金额 | 本次实现盈亏 | 累计实现盈亏 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(events, 1):
        trig = '正常' if e['trigger'] == 'normal' else 'DCA'
        L.append(
            f"| {i} | {e['date']} | {e['tier']} | {trig} | {pct(e['profit_rate'])} | {money(e['price'])} | "
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

    # 对比: V4 vs V3 vs V2 vs V1 vs 纯定投
    L.append("## 七、V4 vs V3 vs V2 vs V1 vs 纯定投 对比")
    L.append("")
    L.append("> 收益口径统一: **总收益 = 期末总资产(持仓市值+回款现金) − 累计定投**。")
    L.append("> 五者均用同一数据区间重跑, 公平对比。V3=10% 起 9 档; V2=永不空仓(每档卖30%); "
             "V1=10/15/20% 且 20% 清仓; 纯定投=不止盈持有到期末。")
    L.append("")
    v3, v2, v1, b = v3_summary, v2_summary, v1_summary, baseline
    L.append("| 指标 | V4(去10%档) | V3(10%起9档) | V2(永不空仓) | V1(20%清仓) | 纯定投不止盈 |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| 止盈次数 | {s['n_events']} | {v3['n_events']} | {v2['n_events']} | {v1['n_events']} | 0 |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(v3['total_sell_proceeds'])} | "
             f"{money(v2['total_sell_proceeds'])} | {money(v1['total_sell_proceeds'])} | 0 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(v3['cum_realized'])} | "
             f"{money(v2['cum_realized'])} | {money(v1['cum_realized'])} | 0 |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(v3['final_value'])} | "
             f"{money(v2['final_value'])} | {money(v1['final_value'])} | {money(b['final_value'])} |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['cash'])} | {money(v3['final_value']+v3['cash'])} | "
             f"{money(v2['final_value']+v2['cash'])} | {money(v1['final_value']+v1['cash'])} | {money(b['final_value'])} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(v3['total_return'])} | "
             f"{pct(v2['total_return'])} | {pct(v1['total_return'])} | {pct(b['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(v3['xirr'])} | {pct(v2['xirr'])} | {pct(v1['xirr'])} | - |")
    L.append("")

    # 核心发现(动态, 基于实际触发数据)
    v4_tr = s['total_return']
    v3_tr = v3['total_return']
    v2_tr = v2['total_return']
    v1_tr = v1['total_return']
    b_tr = b['total_return']
    d_v4_v3 = v4_tr - v3_tr
    d_v4_v2 = v4_tr - v2_tr
    n15_v4 = s['tier_counts'].get('15%', 0)
    n10_v3 = v3['tier_counts'].get('10%', 0)
    peak_v4 = s['peak_profit_rate']
    fifty_triggered = s['tier_counts'].get('50%', 0) > 0
    L.append(f"> **核心发现**: V4 总收益率 {pct(v4_tr)}, V3 为 {pct(v3_tr)}, "
             f"V4 − V3 = {pct(d_v4_v3)}({'高于' if d_v4_v3 > 0 else '低于'} V3); "
             f"V2 为 {pct(v2_tr)}, V4 − V2 = {pct(d_v4_v2)}({'已超' if d_v4_v2 > 0 else '仍低于'} V2); "
             f"V1 {pct(v1_tr)}, 纯定投 {pct(b_tr)}。")
    if not fifty_triggered:
        L.append(f"> **50% 清仓未触发**(同 V3): 本区间 V4 最高持仓收益率 {pct(peak_v4)}, 未达 50% 档, "
                 f"50% 清仓规则未实际生效, V4 全程未空仓。")
    L.append(f"> **去掉 10% 档的效果**: V4 止盈 {s['n_events']} 次(V3 {v3['n_events']} 次, "
             f"少了 {n10_v3} 次 10% 档触发), 15% 档触发 {n15_v4} 次。"
             f"10%~15% 区间不再削薄底仓, 15% 首次触发时持仓更大、锁利基数更高。")
    if d_v4_v3 > 0:
        L.append(f"> V4 高于 V3 的原因: 去掉 10% 档后, 底仓在 10%~15% 小涨中不被削薄, "
                 f"后续 15%+ 触发时持仓更厚, 卖出额与留仓均增加; 同时减少 17 次低档过度交易的机会成本。"
                 f"这**验证了 V3 报告的假设**: 10% 档过早止盈是 V3 弱于 V2 的主因之一, 去掉后收益回升。")
    else:
        L.append(f"> V4 仍{'低于' if d_v4_v3 < 0 else '持平'} V3 的原因: 去掉 10% 档虽减少低档过度交易, "
                 f"但 V3 的 10% 档本身锁利额不大(卖 20% × 低档小持仓), 去掉后边际改善有限; "
                 f"递增卖比在中高位(20%~35% 卖 40%~70%)过度减仓的拖累仍在。")
    if d_v4_v2 > 0:
        L.append(f"> **V4 已反超 V2**({pct(v4_tr)} > {pct(v2_tr)}): 去掉 10% 档 + 递增卖比在高位锁利更充分, "
                 f"在科创50本区间行情中优于 V2 的固定 30% 轻仓止盈。说明「首档 15% + 递增卖比」"
                 f"比「首档 15% + 固定 30%」更适合本行情。")
    else:
        L.append(f"> **V4 仍低于 V2**({pct(v4_tr)} < {pct(v2_tr)}, 差 {pct(d_v4_v2)}): "
                 f"去掉 10% 档缩小了与 V2 的差距, 但递增卖比在 20%~35% 中段(卖 40%~70%)仍过度削薄持仓, "
                 f"底仓薄于 V2(固定 30%), 后续上涨吃到的市值增长仍少于 V2。V2 的「轻仓止盈+永不空仓」"
                 f"在本区间(峰值 {pct(peak_v4)}, 未超 40%)仍是更优配置。")
    L.append(f"> 无论 V4/V3/V2, 止盈总收益仍远低于纯定投({pct(b_tr)}), 根因依旧是**回款闲置零复利**"
             f"--{money(s['cash'])} 元回款趴在现金账户, 错过指数翻倍。最大优化点仍是「回款再投」。")
    L.append("")

    L.append("## 八、可优化方向")
    L.append("")
    L.append("针对科创50 **高波动、强趋势、成长风格** 特性, 在 V4 基础上可考虑:")
    L.append("")
    L.append("1. **回款再投(子弹池复利)**: 当前止盈回款闲置, 零复利。可让回款进入子弹池, 在低位"
             "(收盘价低于 250 日均线 8% 以上)加速抄底, 把高位套现的钱变成低位筹码。"
             "是当前所有止盈版本的最大杠杆, 沪深300 V2 已验证可显著提升总收益。")
    L.append("2. **50% 清仓后回款再投**: V3/V4 的 50% 清仓(本区间未触发)兑现全部浮盈后回款闲置。"
             "若清仓回款在随后下跌中分批再投, 可形成「50% 清仓 -> 低位回补」完整大波段高抛低吸。")
    L.append("3. **递增卖比曲线优化**: V4 卖比 = 2×档位(线性), 在 20%~35% 中段(卖 40%~70%)可能过度减仓。"
             "可改为更平缓的曲线(如 1.5×档位, 15%卖22.5%、20%卖30%…), 或结合波动率--"
             "高波动指数低档就应多锁利, 但中段留仓要厚, 平衡「锁利」与「吃趋势」。需回测对比。")
    L.append("4. **重装阈值动态化**: 当前「跌破 L−2.5% 重装」为固定百分点。可改为跌破 250 日均线或"
             "移动平均成本重装, 更贴合趋势反转; 或给重装加冷却期避免频繁翻转。")
    L.append("5. **DCA 再触发半额阈值调整**: 当前「累计定投 ≥ 上次卖出额一半」即再触发。可调高到 "
             "60%~80% 减少震荡市过度减仓, 或按档位差异化(低档半额、高档更高比例)。")
    L.append("6. **止盈档位动态化**: 当前 15%~50% 固定档。可结合 PE 历史分位、波动率动态调整--"
             "高估区提前止盈、低估区放宽阈值。⚠️ index_info 中科创50的 pe_ratio/pe_percentile "
             "当前为 0(未采集), 落地需先补数据。")
    L.append("7. **首档选择对比**: V4 验证了「去掉 10% 档」的效果。可进一步回测首档 20%(更迟止盈、"
             "底仓更厚)或保留 10% 但降低其卖比(如 10% 卖 10%), 寻找最优首档与卖比组合。")
    L.append("8. **止盈基准优化**: 当前止盈看「组合整体收益率」, 每日新增定投会持续稀释收益率, "
             "导致横盘时收益率被压低、止盈推迟。可改为按「最早批次成本」或「移动平均成本」分批止盈。")
    L.append("")

    L.append("## 九、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, 结果略乐观于真实科创50指数基金定投。")
    L.append("- **去掉 10% 档**: V4 首档 15%, 10%~15% 区间不卖出。V3 的 10% 档(卖 20%)在本区间触发 17 次, "
             "V4 全部避免, 底仓更厚。这是 V4 与 V3 的唯一差异, 用于隔离「10% 档」单一变量。")
    L.append("- **50% 清仓**(本区间未触发): 50% 档卖 100%, 持仓归零(含当日定投份额)。逻辑已用合成数据单测验证。")
    L.append("- **递增卖比**: 同日从低档到高档依次触发时, 每档卖当前持仓的 2L 比例, 累计留存 = ∏(1−2Lᵢ)。")
    L.append("- **DCA 再触发** 按档位独立追踪: 每个档位 L 记录自己的「上次减仓以来累计定投」与"
             "「上次卖出额」, 当 L 未装填、收益率在 [L, L+5%)、且累计定投 ≥ 该档上次卖出额一半时再卖一次。"
             "各档 [L, L+5%) 区间互斥, 同日最多一档 DCA 再触发。DCA 不改 armed 状态, 可连续触发。")
    L.append("- **重装互斥**: 档 L 触发后, 收益率跌破 L−2.5% 才重装。在 [L−2.5%, L) 为等待区"
             "(既不 DCA 也不重装)。重装时清空该档 DCA 状态, 待下次 normal 触发重新建立。")
    L.append("- 卖出按比例结转成本(平均成本法), 单次止盈不改变剩余持仓的平均成本。")
    L.append("- 单日涨幅同时穿越多档时, 各档同日依次触发(每档卖当前 2L 比例), 净效果为分档递减减仓; "
             "穿越到 50% 则清仓。")
    L.append("- XIRR 为资金加权年化, 考虑 6 年陆续投入的资金时间价值, 比简单总额法更严谨; "
             "年化(244日/年)为粗略估算。")
    L.append("- 本报告不构成投资建议。")
    L.append("")
    return "\n".join(L)


def main():
    # 截断到最后一个已确定收盘价的交易日(排除当天盘中未定数据, 保证可复现)
    from datetime import date, timedelta
    prices = fetch_prices(end_date=date.today() - timedelta(days=1))
    if not prices:
        print("未取到科创50行情数据", file=sys.stderr)
        sys.exit(1)

    events, summary = run_backtest_v4(prices)
    _v3_events, v3_summary = run_backtest_v3(prices)        # 同区间重跑 V3, 公平对比
    _v2_events, v2_summary = run_backtest_v2(prices)        # 同区间重跑 V2
    _v1_events, v1_summary = run_v1_backtest(prices, rearm_mode='on_clear')
    baseline = _pure_dca_baseline(prices)

    report = build_report(events, summary, v3_summary, v2_summary, v1_summary, baseline)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    s = summary
    print(f"V4 回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 交易日)")
    print(f"累计定投: {money(s['total_invested'])} 元")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(正常 {s['trigger_counts'].get('normal',0)} / DCA 再触发 {s['trigger_counts'].get('dca_retrigger',0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮盈: {money(s['unrealized'])} 元 | 现金: {money(s['cash'])} 元")
    print(f"V4 总收益: {money(s['total_profit'])} | 总收益率: {pct(s['total_return'])} | "
          f"年化: {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"[对比] V3 总收益率: {pct(v3_summary['total_return'])} | XIRR: {pct(v3_summary['xirr'])} | "
          f"止盈 {v3_summary['n_events']} 次")
    print(f"[对比] V2 总收益率: {pct(v2_summary['total_return'])} | XIRR: {pct(v2_summary['xirr'])} | "
          f"止盈 {v2_summary['n_events']} 次")
    print(f"[对比] V1 总收益率: {pct(v1_summary['total_return'])} | 止盈 {v1_summary['n_events']} 次")
    print(f"[对比] 纯定投不止盈 总收益率: {pct(baseline['total_return'])}")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
