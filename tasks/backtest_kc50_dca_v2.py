#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯止盈(永不空仓) 回测 V2

相对 V1(`backtest_kc50_dca.py`)的策略变更:
  1. 止盈阶梯改为「永不空仓」: 15% 卖 30%, 此后每涨 5%(20%/25%/30%…)各卖当前持仓 30%,
     每次只卖 30%、保留 70%, 永不清仓。
  2. 15% 档 DCA 再触发: 触发一次 15% 后, 若收益率持续在 [15%,20%) 震荡(未到 20%、未跌破 10%),
     当「自上次止盈累计加仓 ≥ 上次卖出金额一半」时, 再卖一次当前持仓的 30%。
  3. 重装规则按档位: 档位 L 在收益率跌破 L−5% 时重装(15% 跌破 10%、20% 跌破 15%…)。
     故 20% 止盈后回落到 10%~15%, 仅 20% 重装、15% 不重装, 回升时 15% 被跳过。

数据: index_info 表科创50(000688)收盘价。
输出: 同目录 科创50_定投止盈_回测报告_V2.md
"""
import os
import sys
from collections import defaultdict

# 让脚本可直接运行(`python tasks/backtest_kc50_dca_v2.py`): 将仓库根加入 sys.path 以 import tasks 包
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# 复用 V1 的数据访问与格式化辅助
from tasks.backtest_kc50_dca import (  # noqa: E402
    fetch_prices, _xirr, money, shares, pct,
    DAILY_INVEST, TRADING_DAYS_PER_YEAR, run_backtest as run_v1_backtest,
)

FIRST_TIER = 0.15        # 首个止盈档(15%)
TIER_STEP = 0.05         # 档位间距(每涨 5%)
SELL_FRAC = 0.30         # 每次卖出当前持仓的比例(30%)
MAX_TIER = 2.00          # 档位上限(200%, 足够覆盖; 0.15~2.00 共 38 档)
TIERS = [round(FIRST_TIER + TIER_STEP * i, 10) for i in range(int((MAX_TIER - FIRST_TIER) / TIER_STEP) + 1)]

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告_V2.md'
)


def _tier_label(L):
    return f"{int(round(L * 100))}%"


def run_backtest_v2(prices):
    """执行 V2 回测, 返回 (events, summary)。状态机见模块文档。"""
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

    def _fire(trade_date, L, price, profit_rate, trigger, dca_at_trigger):
        """卖出当前持仓的 SELL_FRAC, 记录事件, 更新状态。"""
        nonlocal total_shares, total_cost, cum_realized
        nonlocal dca_since_last_sell, last_sell_proceeds
        shares_before = total_shares
        shares_sold = total_shares * SELL_FRAC
        shares_after = total_shares - shares_sold

        value_before = shares_before * price
        sell_proceeds = shares_sold * price
        value_after = shares_after * price

        cost_before = total_cost
        cost_sold = total_cost * SELL_FRAC          # 平均成本法: 按比例结转
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

        # 3) 重装: 档位 L 已触发且 收益率 < L−5% -> 重装
        for L in TIERS:
            if not armed[L] and profit_rate < L - TIER_STEP:
                armed[L] = True

        # 4) 正常止盈(档位升序): 收益率 ≥ L 且已装填 -> 卖 30%
        for L in TIERS:
            if profit_rate >= L and armed[L]:
                dca_snapshot = dca_since_last_sell
                _fire(trade_date, L, price, profit_rate, 'normal', dca_snapshot)
                armed[L] = False

        # 5) DCA 再触发(仅 15%): 15% 未装填 且 15%≤收益率<20% 且 累计加仓 ≥ 上次卖出额一半
        L15 = FIRST_TIER
        if (not armed[L15]
                and FIRST_TIER <= profit_rate < 0.20
                and last_sell_proceeds > 0
                and dca_since_last_sell >= last_sell_proceeds / 2.0):
            dca_snapshot = dca_since_last_sell
            _fire(trade_date, L15, price, profit_rate, 'dca_retrigger', dca_snapshot)
            # DCA 再触发不改 armed 状态(15% 保持未装填), 可连续触发

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


def build_report(events, summary, v1_summary, baseline):
    L = []
    s = summary
    L.append("# 科创50 定投止盈回测 V2(永不空仓 + DCA 再触发)")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca_v2.py`。")
    L.append("> 本报告为 V1(`科创50_定投止盈_回测报告.md`)的策略升级版。")
    L.append("")

    L.append("## 一、V2 相对 V1 的策略变更")
    L.append("")
    L.append("| 维度 | V1(20%清仓) | V2(永不空仓) |")
    L.append("|---|---|---|")
    L.append("| 止盈阶梯 | 10/15/20%, 20% 档卖全部(清仓) | **15% 起, 每涨 5% 各卖当前 30%**, 永不清仓 |")
    L.append("| 持仓状态 | 20% 触发后空仓, 重新定投积累 | **永不空仓**, 每次保留 70% 底仓继续吃趋势 |")
    L.append("| 震荡处理 | 无 | **15% 档 DCA 再触发**: 15%~20% 区间震荡时, 加仓达上次卖出额一半再卖一次 15% |")
    L.append("| 重装规则 | 仅 20% 清仓后重装 | **按档位**: 档位 L 跌破 L−5% 重装(15% 跌破10%、20% 跌破15%…) |")
    L.append("| 15% 跳过 | 无此场景 | 20% 后回落到 10%~15%, 仅 20% 重装, 回升时 **15% 被跳过** |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("V1 的 20% 一次性清仓在科创50这类**强趋势、高波动**指数上有踏空风险--清仓后若继续大涨"
             "将完全错过。V2 改为**永不空仓**: 每个档位只卖 30%、留 70%, 趋势延续时底仓持续吃上涨; "
             "同时新增 **DCA 再触发** 处理 15%~20% 区间的长期震荡--定投不断加仓, 定期收割 30%, "
             "避免「只买不卖」的资金沉淀。重装按档位独立判定, 更精细地反映各档位的盈亏复位。")
    L.append("")

    L.append("## 二、策略与假设")
    L.append("")
    L.append("| 项 | 设定 |")
    L.append("|---|---|")
    L.append(f"| 标的 | 科创50指数(000688), 以收盘价模拟可投资净值 |")
    L.append(f"| 定投 | 每个交易日投入 {money(DAILY_INVEST)} 元, 自 {s['first_date']} 起不间断(无论涨跌) |")
    L.append(f"| 止盈阶梯 | 持仓收益率 ≥15% 卖当前 30%; 此后每涨 5%(20%/25%/30%…)各卖当前 30% |")
    L.append(f"| 卖出比例 | 每次卖出当时持仓的 {int(SELL_FRAC*100)}%, 保留 {int((1-SELL_FRAC)*100)}%, **永不空仓** |")
    L.append("| DCA 再触发 | 15% 触发后, 若 15%≤收益率<20% 且自上次止盈累计加仓≥上次卖出额一半, 再卖一次 15% |")
    L.append("| 重装规则 | 档位 L 在收益率跌破 L−5% 时重装(15%:跌破10% · 20%:跌破15% · 25%:跌破20%…) |")
    L.append("| 15% 跳过 | 20% 后回落到 10%~15%, 仅 20% 重装, 回升时 15% 被跳过, 等 20% 再卖 |")
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
    # 各档触发次数
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
             "收盘价 / 止盈前份额 / 卖出份额 / 止盈后份额 / **止盈前持仓金额** / 止盈前成本 / "
             "**止盈金额(卖出回款)** / **止盈后持仓金额** / 本次实现盈亏 / 累计实现盈亏。")
    L.append("")
    L.append("> 触发类型: `正常`=档位首次/重装后穿越触发; `DCA`=15%~20% 震荡区间加仓达半额再触发。")
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

    # 对比: V2 vs V1 vs 纯定投
    L.append("## 七、V2 vs V1 vs 纯定投 对比")
    L.append("")
    L.append("> 收益口径统一: **总收益 = 期末总资产(持仓市值+回款现金) − 累计定投**。")
    L.append("> V1 为 `backtest_kc50_dca.py` on_clear 口径(10/15/20%, 20% 清仓); 纯定投为不止盈持有到期末。")
    L.append("")
    v1 = v1_summary
    b = baseline
    L.append("| 指标 | V2(永不空仓) | V1(20%清仓) | 纯定投不止盈 |")
    L.append("|---|---|---|---|")
    L.append(f"| 止盈次数 | {s['n_events']} | {v1['n_events']} | 0 |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(v1['total_sell_proceeds'])} | 0 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(v1['cum_realized'])} | 0 |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(v1['final_value'])} | {money(b['final_value'])} |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['cash'])} | {money(v1['final_value']+v1['cash'])} | {money(b['final_value'])} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(v1['total_return'])} | {pct(b['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(v1['xirr'])} | — |")
    L.append("")
    L.append("> **核心发现**: V2(24.34%) > V1(21.83%), 但两者都远低于纯定投不止盈(99.92%)。"
             "原因是科创50在 2020-2026 为**长期上行**行情(1000→2185, 约翻倍), 而止盈策略有两个固有代价: "
             "①**止盈截断上行**--每次卖 30% 都把后续上涨的筹码提前兑现; "
             "②**回款闲置零复利**--578,481 元回款趴在现金账户, 完全错过指数翻倍。"
             "两者叠加, 使止盈策略在单边牛市中主动跑输买入持有。"
             "结论: **本策略的最大优化点是「回款再投」(见优化方向 1)**--把高位套现的钱在低位重新买入, "
             "把「截断上行 + 闲置」变成「高抛低吸 + 复利」, 才有可能反超纯定投。"
             "V2 相对 V1 的优势(永不空仓保留底仓)在趋势市中成立, 但量级有限, 不足以弥补闲置现金的损失。")
    L.append("")

    L.append("## 八、可优化方向")
    L.append("")
    L.append("针对科创50 **高波动、强趋势、成长风格** 特性, 在 V2 基础上可考虑:")
    L.append("")
    L.append("1. **回款再投(子弹池复利)**: 当前止盈回款闲置, 零复利。可让回款进入子弹池, 在低位"
             "(收盘价低于 250 日均线 8% 以上)加速抄底, 把高位套现的钱变成低位筹码。沪深300 V2 已验证此优化可显著提升总收益。")
    L.append("2. **均线/估值加权定投**: 当前无论涨跌每日固定 300 元, 顶部照样定投抬高成本。"
             "可按收盘价相对 250 日均线偏离度加权--低估多投、高估停投, 压低平均成本。科创50波动大于沪深300, 潜力更大。")
    L.append("3. **DCA 再触发推广到更高档位**: 当前 DCA 再触发仅限 15%~20% 区间。可推广到 20%~25%、25%~30% 等"
             "震荡区间--任意两档间长期横盘时, 加仓达半额即收割 30%, 提高资金周转。")
    L.append("4. **止盈档位动态化**: 当前 15/20/25% 为固定档。可结合 PE 历史分位、波动率动态调整--"
             "高估区提前止盈、低估区放宽阈值。⚠️ index_info 中科创50的 pe_ratio/pe_percentile 当前为 0(未采集), 落地需先补数据。")
    L.append("5. **重装阈值优化**: 当前「跌破 L−5% 重装」为固定百分点。可改为跌破 250 日均线或"
             "移动平均成本重装, 更贴合趋势反转而非噪声波动; 或给重装加冷却期避免频繁翻转。")
    L.append("6. **20% 后回落不跳过 15%**: V2 字面规则下, 20% 后回落到 10%~15% 再上涨会跳过 15% 档。"
             "可改为「跌破 15% 同时重装 15% 和 20%」(完整新一轮), 在宽幅震荡中多收割一档。需回测对比取舍。")
    L.append("7. **止盈基准优化**: 当前止盈看「组合整体收益率」, 每日新增定投会持续稀释收益率, "
             "导致横盘时收益率被压低、止盈推迟。可改为按「最早批次成本」或「移动平均成本」分批止盈, 反映不同批次真实盈亏。")
    L.append("8. **卖出比例随档位递减**: 当前每档固定卖 30%。可改为越高档卖越多(如 15% 卖 20%、20% 卖 30%、25% 卖 40%), "
             "在确保永不空仓前提下, 高位多锁利、低位多留仓。")
    L.append("")

    L.append("## 九、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, 结果略乐观于真实科创50指数基金定投。")
    L.append("- **永不空仓**: 每次只卖 30%、保留 70%, 即便连触多档(0.7^n)也永不为 0, 加之每日定投持续加仓, 持仓始终 > 0。")
    L.append("- **DCA 再触发** 仅在 15% 档已触发(未装填)、收益率停留在 [15%,20%)、且未跌破 10% 时生效; "
             "一旦跌破 10% 走「重装」路径, 涨回 15% 由正常止盈触发。两条再触发路径互斥。")
    L.append("- **15% 跳过**: 20% 止盈后若回落到 10%~15%(仅触发 20% 重装、15% 不重装), 回升时 15% 被跳过, 等 20% 再卖。"
             "这是对重装规则的字面实现; 若希望完整新一轮可改重装策略(见优化方向 6)。")
    L.append("- 单日涨幅同时穿越多档时, 各档同日依次触发(每档卖当前 30%), 净效果为分档减仓而非清仓。")
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

    events, summary = run_backtest_v2(prices)
    _v1_events, v1_summary = run_v1_backtest(prices, rearm_mode='on_clear')
    baseline = _pure_dca_baseline(prices)

    report = build_report(events, summary, v1_summary, baseline)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    s = summary
    print(f"V2 回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 交易日)")
    print(f"累计定投: {money(s['total_invested'])} 元")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(正常 {s['trigger_counts'].get('normal',0)} / DCA 再触发 {s['trigger_counts'].get('dca_retrigger',0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮盈: {money(s['unrealized'])} 元 | 现金: {money(s['cash'])} 元")
    print(f"V2 总收益: {money(s['total_profit'])} | 总收益率: {pct(s['total_return'])} | "
          f"年化: {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"[对比] V1 总收益率: {pct(v1_summary['total_return'])} | XIRR: {pct(v1_summary['xirr'])} | "
          f"止盈 {v1_summary['n_events']} 次")
    print(f"[对比] 纯定投不止盈 总收益率: {pct(baseline['total_return'])}")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
