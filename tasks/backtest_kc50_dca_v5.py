#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯止盈(永不空仓) + 子弹池复利 + 迟滞重装 回测 V5

相对 V4(`backtest_kc50_dca_v4.py`)的核心优化(迟滞重装, 落地 V3 优化方向 4):
  档位 L 在收益率跌破 **L−2.5%** 时重装(V4/V3 是跌破 L, V2 是跌破 L−5%)。
  增加 2.5% 迟滞带, 防止震荡市小幅回撤即重装导致的高频卖出 -- V3 消融表显示优化6
  (跌破L重装)使 15% 档在宽幅震荡中频繁触发(止盈 +7 次), 迟滞带正是针对性降噪。

引擎用 rearm_offset 参数化重装阈值的下偏量:
  - rearm_offset=0.025(V5 默认): 跌破 L−2.5%
  - rearm_offset=0.0: 跌破 L(=V4/V3 opt6=True)
  - rearm_offset=0.05: 跌破 L−5%(=V2 opt6=False)
  rearm_offset=0.0 且 reinvest=False 精确复现 V4; rearm_offset=0.05 且 opt3=opt8=False 复现 V2。

其余完全继承 V4: 永不空仓(opt8 分档卖出) + DCA 全档(opt3) + 子弹池复利(reinvest)。
数据: index_info 表科创50(000688)收盘价。
输出: 同目录 科创50_定投止盈_回测报告_V5.md
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
# 复用 V2/V3/V4 用于回归校验与对比
from tasks.backtest_kc50_dca_v2 import run_backtest_v2  # noqa: E402
from tasks.backtest_kc50_dca_v3 import (  # noqa: E402
    run_backtest_v3, sell_frac, _tier_label,
    FIRST_TIER, TIER_STEP, TIERS,
    SELL_FRAC_BASE, SELL_FRAC_STEP, SELL_FRAC_CAP,
    _pure_dca_baseline, _sell_frac_table,
)
from tasks.backtest_kc50_dca_v4 import (  # noqa: E402
    run_backtest_v4,
    _reinvest_mult, _reinvest_target,
    MA_WINDOW, MA_WARMUP,
    REINVEST_D_THRESHOLD, REINVEST_MULT, REINVEST_MULT_DEEP, POOL_DRAIN_FRAC,
)

REARM_OFFSET_V5 = 0.025    # V5 默认迟滞带: 档 L 跌破 L−2.5% 才重装

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告_V5.md'
)


def run_backtest_v5(prices, opt3=True, opt8=True, rearm_offset=REARM_OFFSET_V5, reinvest=True):
    """执行 V5 回测, 返回 (events, summary, by_year_pool)。

    opt3: DCA 再触发推广到所有档位(True) / 仅 15%(False, V2)
    opt8: 卖出比例随档位递增(True) / 固定 30%(False, V2)
    rearm_offset: 重装阈值的下偏量。档 L 跌破 L−rearm_offset 时重装。
        0.025(V5 默认)=跌破L−2.5% · 0.0=跌破L(V4/V3) · 0.05=跌破L−5%(V2)
    reinvest: 止盈回款入子弹池并在低位(d≤-8%)加速再投(True, V4/V5) / 回款闲置(False)
    rearm_offset=0.0 且 reinvest=False 精确复现 V4; rearm_offset=0.05 且 opt3=opt8=False 复现 V2。
    """
    armed = {L: True for L in TIERS}      # 各档是否装填
    total_shares = 0.0                    # 当前持仓份额
    total_cost = 0.0                      # 当前持仓成本(卖出按比例结转; 子弹池再投累入)
    total_invested = 0.0                  # 累计定投金额(外部本金, 与 V4 一致)
    cum_reinvested = 0.0                  # 累计子弹池再投金额(内部循环, 不计外部本金)
    cum_realized = 0.0                    # 累计实现盈亏
    bullet_pool = 0.0                     # 子弹池现金(回款累积 - 低位再投消耗)
    dca_since_last_sell = 0.0             # 自上次止盈以来的累计加仓金额
    last_sell_proceeds = 0.0              # 上一次卖出金额(用于 DCA 再触发半额判定)

    events = []
    peak_profit_rate = 0.0
    daily_cf = []                         # XIRR 现金流: 仅外部资金(每日定投流出 + 期末总资产流入)
    history = []                          # 收盘价序列(用于 MA250)

    by_year_pool = defaultdict(lambda: {'inflow': 0.0, 'outflow': 0.0, 'end': 0.0})

    def _fire(trade_date, L, price, profit_rate, trigger, dca_at_trigger, frac, d):
        """卖出当前持仓的 frac, 回款入子弹池, 记录事件, 更新状态。"""
        nonlocal total_shares, total_cost, cum_realized
        nonlocal dca_since_last_sell, last_sell_proceeds, bullet_pool
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
        bullet_pool += sell_proceeds           # 回款入子弹池
        by_year_pool[trade_date.year]['inflow'] += sell_proceeds
        last_sell_proceeds = sell_proceeds
        dca_since_last_sell = 0.0

        events.append({
            'date': trade_date,
            'tier': _tier_label(L),
            'trigger': trigger,                 # 'normal' | 'dca_retrigger'
            'profit_rate': profit_rate,
            'price': price,
            'd': d,                             # 当日均线偏离度(估值锚, 事件记录用)
            'sell_frac': frac,                  # 本档卖出比例(优化8)
            'avg_cost': cost_before / shares_before if shares_before else 0.0,
            'shares_before': shares_before,
            'shares_sold': shares_sold,
            'shares_after': shares_after,
            'value_before': value_before,       # 止盈前持仓金额(市值)
            'cost_before': cost_before,
            'cost_after': cost_after,
            'sell_proceeds': sell_proceeds,     # 止盈金额(卖出回款, 入池)
            'value_after': value_after,         # 止盈后持仓金额(市值)
            'realized': realized,
            'cum_realized': cum_realized,
            'dca_at_trigger': dca_at_trigger,
            'pool_after': bullet_pool,          # 止盈后子弹池余额
        })

    for trade_date, price in prices:
        history.append(price)
        year = trade_date.year

        # 0) 均线偏离度 d(估值锚; 供子弹池再投与事件记录; 计算不改变任何持仓状态)
        if len(history) < MA_WARMUP:
            d = 0.0
        else:
            window = history[-MA_WINDOW:]
            ma = sum(window) / len(window)
            d = (price - ma) / ma if ma else 0.0

        # 1) 每日定投买入(固定 300, 与 V4 一致 -- 不引入均线加权定投)
        buy_shares = DAILY_INVEST / price
        total_shares += buy_shares
        total_cost += DAILY_INVEST
        total_invested += DAILY_INVEST
        daily_cf.append((trade_date, -DAILY_INVEST))
        dca_since_last_sell += DAILY_INVEST

        # 2) 子弹池低位加速再投(仅 reinvest=True; d≤-8% 且池有余额)
        if reinvest and _reinvest_mult(d) > 0 and bullet_pool > 0:
            target = _reinvest_target(bullet_pool, DAILY_INVEST, d)
            extra = min(bullet_pool, target)
            if extra > 0:
                sh = extra / price
                total_shares += sh
                total_cost += extra              # 再投额累入成本(内部资金, 不计 total_invested)
                cum_reinvested += extra
                bullet_pool -= extra
                by_year_pool[year]['outflow'] += extra

        # 3) 持仓收益率
        profit_rate = (total_shares * price - total_cost) / total_cost if total_cost > 0 else 0.0
        if profit_rate > peak_profit_rate:
            peak_profit_rate = profit_rate

        # 4) 重装(迟滞带): 档 L 已触发 且 收益率跌破 L−rearm_threshold_offset -> 重装
        #    V5: rearm_offset=0.025 -> 跌破 L−2.5%; V4: 0.0 -> 跌破 L; V2: 0.05 -> 跌破 L−5%
        for L in TIERS:
            if not armed[L]:
                rearm_threshold = L - rearm_offset
                if profit_rate < rearm_threshold:
                    armed[L] = True

        # 5) 正常止盈(档位升序): 收益率 ≥ L 且已装填 -> 卖 sell_frac(L), 回款入池
        for L in TIERS:
            if profit_rate >= L and armed[L]:
                _fire(trade_date, L, price, profit_rate, 'normal', dca_since_last_sell,
                      sell_frac(L, opt8), d)
                armed[L] = False

        # 6) DCA 再触发: 档 L 未装填 且 收益率停留在 [L, L+5%) 且 累计加仓 ≥ 上次卖出额一半
        dca_tiers = TIERS if opt3 else [FIRST_TIER]
        for L in dca_tiers:
            if (not armed[L]
                    and L <= profit_rate < L + TIER_STEP
                    and last_sell_proceeds > 0
                    and dca_since_last_sell >= last_sell_proceeds / 2.0):
                _fire(trade_date, L, price, profit_rate, 'dca_retrigger', dca_since_last_sell,
                      sell_frac(L, opt8), d)
                break

        by_year_pool[year]['end'] = bullet_pool

    # 期末状态
    final_price = prices[-1][1]
    final_value = total_shares * final_price
    unrealized = final_value - total_cost
    total_sell_proceeds = sum(e['sell_proceeds'] for e in events)
    # 净外部本金 = 仅累计定投; 子弹池再投是内部资金循环, 不计入本金
    total_profit = final_value + bullet_pool - total_invested
    total_return = total_profit / total_invested if total_invested else 0.0

    n_days = len(prices)
    years = n_days / TRADING_DAYS_PER_YEAR
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0

    # XIRR: 外部现金流(每日定投流出 + 期末总资产流入), 子弹池再投为内部循环不计入
    daily_cf.append((prices[-1][0], final_value + bullet_pool))
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
        'total_invested': total_invested,          # 外部本金(与 V4 一致)
        'cum_reinvested': cum_reinvested,          # 子弹池再投(内部循环)
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
        'bullet_pool': bullet_pool,                # 期末子弹池余额 = 闲置现金
        'cash': bullet_pool,                       # 别名(与 V3/V4 口径对齐: 期末现金)
        'total_profit': total_profit,
        'total_return': total_return,
        'annualized': annualized,
        'peak_profit_rate': peak_profit_rate,
        'xirr': xirr_val,
        'opt3': opt3, 'opt8': opt8, 'rearm_offset': rearm_offset, 'reinvest': reinvest,
    }
    return events, summary, dict(by_year_pool)


def _ablation_row(label, s):
    return (f"| {label} | {s['n_events']} | "
            f"{s['trigger_counts'].get('normal', 0)}/{s['trigger_counts'].get('dca_retrigger', 0)} | "
            f"{money(s['total_sell_proceeds'])} | {money(s.get('cum_reinvested', 0.0))} | "
            f"{money(s['cum_realized'])} | {money(s['final_value'])} | "
            f"{money(s['bullet_pool'])} | {money(s['final_value'] + s['bullet_pool'])} | "
            f"{pct(s['total_return'])} | {pct(s['xirr'])} |")


def _sens_row(label,口径, s):
    return (f"| {label} | {口径} | {s['n_events']} | {s['tier_counts'].get('15%', 0)} | "
            f"{money(s['total_sell_proceeds'])} | {money(s.get('cum_reinvested', 0.0))} | "
            f"{money(s['cum_realized'])} | {money(s['final_value'])} | {money(s['bullet_pool'])} | "
            f"{money(s['final_value'] + s['bullet_pool'])} | {pct(s['total_return'])} | {pct(s['xirr'])} |")


def build_report(events, summary, by_year_pool, v4_summary, v3_summary, v2_summary, v1_summary, baseline,
                 abl, sens):
    """生成 V5 报告。

    abl = {'v4':s(V4 口径, rearm_offset=0.0+子弹池), 'v5':s(V5, rearm_offset=0.025+子弹池)} 迟滞边际消融。
    sens = [(标签, 口径, s), ...] 迟滞带宽度敏感性(reinvest=True, 仅变 rearm_offset)。
    """
    L = []
    s = summary
    L.append("# 科创50 定投止盈回测 V5(永不空仓 + 子弹池复利 + 迟滞重装)")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca_v5.py`。")
    L.append("> 本报告为 V4(`科创50_定投止盈_回测报告_V4.md`)的策略升级版, 落地 V3 优化方向 4(重装冷却/迟滞)。")
    L.append("")

    # 一、策略变更
    L.append("## 一、V5 相对 V4 的策略变更")
    L.append("")
    L.append("| 维度 | V4 | V5 |")
    L.append("|---|---|---|")
    L.append("| 重装阈值 | 档 L 跌破 **L**(自身档位)即重装 | 档 L 跌破 **L−2.5%** 才重装(2.5% 迟滞带) |")
    L.append("| 15% 档重装 | 收益率跌破 15% 即重装 | 收益率跌破 **12.5%** 才重装 |")
    L.append("| 20% 档重装 | 跌破 20% 即重装 | 跌破 **17.5%** 才重装 |")
    L.append("| 震荡市行为 | 小幅回撤(如 14%)即重装 15%, 回升再卖 -> **高频卖出** | [12.5%,15%) 内不重装, 回升不再卖 15% -> **降噪** |")
    L.append("| 子弹池复利 | 继承(回款入池, 低位再投) | **完全继承 V4**, 不改动 |")
    L.append("| 每日定投 / 止盈 / DCA | opt8/opt3(继承 V3) | **完全继承 V4**, 不改动 |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("V3 消融表已揭示: 优化6(跌破 L 重装)虽 +1.21% 收益, 代价是正常止盈 +7 次--"
             "在宽幅震荡中, 收益率在 L 附近反复穿越, 每次小幅回撤(如从 15.1% 跌到 14.9%)即触发 15% 档重装, "
             "回升再卖一次, 造成 15% 档高频触发、过早减仓。V5 引入 **2.5% 迟滞带**: 档 L 触发后, "
             "必须收益率跌破 **L−2.5%** 才重装(15% 档要跌破 12.5%), [L−2.5%, L) 区间内的噪声回撤不再触发重装, "
             "从而抑制震荡市的高频卖出。迟滞带宽度 2.5% 介于 V2(5%, 过宽致跳过 15% 档)与 V4(0, 无迟滞致高频)之间, "
             "在「不跳过档位」与「不过度触发」间取折中。")
    L.append("")
    L.append("V5 在 V4 基础上**仅改动重装阈值**(L -> L−2.5%), 子弹池复利、分档卖出、DCA 全档全部继承 V4, "
             "故 V5 vs V4 是「同子弹池、同止盈比例、只差重装迟滞」的干净对照。"
             "引擎用 `rearm_offset` 参数化迟滞带宽度: 0.0=跌破L(V4) · 0.025=跌破L−2.5%(V5) · 0.05=跌破L−5%(V2), "
             "`rearm_offset=0.0` 且 `reinvest=False` 精确复现 V4(回归校验)。")
    L.append("")

    # 二、策略与假设
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
    L.append(f"| **重装规则(V5 核心)** | 档 L 在收益率跌破 **L−{REARM_OFFSET_V5*100:g}%** 时重装"
             f"(15%:跌破12.5% · 20%:跌破17.5% · 25%:跌破22.5%…); [L−2.5%, L) 内不重装 |")
    L.append(f"| 均线(估值锚) | {MA_WINDOW} 日简单均线(MA{MA_WINDOW}); 不足 {MA_WARMUP} 日无信号(d=0, 不触发再投), "
             f"之后按可用窗口(最多 {MA_WINDOW} 日)计算 -- 与沪深300 V2 一致 |")
    L.append(f"| 子弹池再投(优化1) | d≤{int(REINVEST_D_THRESHOLD*100)}% 启动; 每日再投目标 = 池余额×{int(POOL_DRAIN_FRAC*100)}% "
             f"+ 当日定投额×加速倍数, 实际再投 min(池余额, 目标); "
             f"-8%~-20% 加速 {int(REINVEST_MULT)}x、≤-20% 加速 {int(REINVEST_MULT_DEEP)}x |")
    L.append("| 持仓收益率 | (持仓市值 − 持仓成本) / 持仓成本; 子弹池低位再投会压低成本、抬高收益率 |")
    L.append("| 成本结转 | 卖出按比例结转成本(平均成本法); 子弹池再投额按买入价累入成本 |")
    L.append("| 每日顺序 | 先定投买入, 再子弹池低位再投, 再判定止盈(迟滞重装 -> 正常止盈 -> DCA 再触发) |")
    L.append("| 回款处理 | 止盈回款**入子弹池**(继承 V4); 低位再投消耗子弹池; 期末余额作现金 |")
    L.append("| 费用 | 不计交易费用、分红再投、税收; 指数点位近似可投资(可买碎额) |")
    L.append("")
    L.append("### 优化8 卖出比例表(继承 V3/V4)")
    L.append("")
    L.append("| 档位 | 卖出比例 | 留存比例 |")
    L.append("|---|---|---|")
    for label, frac in _sell_frac_table():
        L.append(f"| {label} | {int(round(frac * 100))}% | {int(round((1 - frac) * 100))}% |")
    L.append(f"| ≥50% | {int(SELL_FRAC_CAP * 100)}%(封顶) | {int(round((1 - SELL_FRAC_CAP) * 100))}% |")
    L.append("")
    L.append("### 各档重装阈值对比(V2 / V4 / V5)")
    L.append("")
    L.append("| 档位 L | V2(跌破L−5%) | V4(跌破L) | **V5(跌破L−2.5%)** |")
    L.append("|---|---|---|---|")
    for L_tier in [0.15, 0.20, 0.25, 0.30]:
        L.append(f"| {int(L_tier*100)}% | 跌破{int((L_tier-0.05)*100)}% | 跌破{int(L_tier*100)}% | "
                 f"跌破{(L_tier-REARM_OFFSET_V5)*100:g}% |")
    L.append("")

    # 三、数据概览
    L.append("## 三、数据概览")
    L.append("")
    L.append("| 项 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 交易日数 | {s['n_days']} |")
    L.append(f"| 回测区间 | {s['first_date']} ~ {s['last_date']} |")
    L.append(f"| 收盘价区间 | {money(s['min_price'])} ~ {money(s['max_price'])} |")
    L.append(f"| 区间内最高持仓收益率 | {pct(s['peak_profit_rate'])} |")
    L.append("")

    # 四、回测汇总
    L.append("## 四、回测汇总")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 累计定投金额(外部本金) | {money(s['total_invested'])} 元 |")
    L.append(f"| 子弹池再投金额(内部循环) | {money(s['cum_reinvested'])} 元 |")
    L.append(f"| 净外部本金(仅累计定投) | {money(s['total_invested'])} 元 |")
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
    L.append(f"| 期末子弹池现金 | {money(s['bullet_pool'])} 元 |")
    L.append(f"| 期末总资产(市值+子弹池) | {money(s['final_value'] + s['bullet_pool'])} 元 |")
    L.append(f"| 总收益(期末总资产−净外部本金) | {money(s['total_profit'])} 元 |")
    L.append(f"| 总收益率(简单总额法) | {pct(s['total_return'])} |")
    L.append(f"| 年化收益率(估, 244日/年) | {pct(s['annualized'])} |")
    L.append(f"| XIRR(外部现金流年化) | {pct(s['xirr'])} |")
    L.append("")
    L.append("### 各档触发次数")
    L.append("")
    L.append("| 档位 | 次数 |")
    L.append("|---|---|")
    for L_tier in sorted(s['tier_counts'], key=lambda x: int(x[:-1])):
        L.append(f"| {L_tier} | {s['tier_counts'][L_tier]} 次 |")
    L.append("")

    # 五、止盈事件明细
    L.append("## 五、止盈事件明细")
    L.append("")
    L.append(f"共 {s['n_events']} 次止盈。下表逐次记录: 触发日期 / 档位 / 触发类型 / 触发时持仓收益率 / "
             "收盘价 / **均线偏离** / 卖出比例 / 止盈前份额 / 卖出份额 / 止盈后份额 / **止盈前持仓金额** / "
             "止盈前成本 / **止盈金额(入池回款)** / **止盈后持仓金额** / 本次实现盈亏 / 累计实现盈亏 / **止盈后子弹池**。")
    L.append("")
    L.append("> 触发类型: `正常`=档位首次/重装后穿越触发; `DCA`=任意两档间震荡区间加仓达半额再触发。")
    L.append("> 均线偏离 d = 收盘价/MA250 − 1; d 为正表示高于均线(高位区), 止盈多发生在 d 显著为正时。")
    L.append("")
    L.append("| # | 日期 | 档位 | 类型 | 触发收益率 | 收盘价 | 均线偏离 | 卖出比例 | 止盈前份额 | 卖出份额 | 止盈后份额 | "
             "止盈前持仓金额 | 止盈前成本 | 止盈金额 | 止盈后持仓金额 | 本次实现盈亏 | 累计实现盈亏 | 止盈后子弹池 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(events, 1):
        trig = '正常' if e['trigger'] == 'normal' else 'DCA'
        L.append(
            f"| {i} | {e['date']} | {e['tier']} | {trig} | {pct(e['profit_rate'])} | {money(e['price'])} | "
            f"{pct(e['d'])} | {int(round(e['sell_frac'] * 100))}% | "
            f"{shares(e['shares_before'])} | {shares(e['shares_sold'])} | {shares(e['shares_after'])} | "
            f"{money(e['value_before'])} | {money(e['cost_before'])} | {money(e['sell_proceeds'])} | "
            f"{money(e['value_after'])} | {money(e['realized'])} | {money(e['cum_realized'])} | "
            f"{money(e['pool_after'])} |"
        )
    L.append("")

    # 六、止盈事件按年分布
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

    # 七、子弹池运作(按年)
    L.append("## 七、子弹池运作(按年)- 复利核心(继承 V4)")
    L.append("")
    L.append("子弹池 = 止盈回款累积的现金; 低估日(d ≤ -8%)从池中取钱加速抄底。"
             "下表展示每年**流入(止盈回款)-> 流出(低位再投)-> 年末余额**(机制与 V4 完全一致)。")
    L.append("")
    L.append("| 年份 | 流入(止盈回款) | 流出(低位再投) | 年末子弹池余额 |")
    L.append("|---|---|---|---|")
    for y in sorted(by_year_pool):
        p = by_year_pool[y]
        L.append(f"| {y} | {money(p['inflow'])} | {money(p['outflow'])} | {money(p['end'])} |")
    L.append("")
    L.append(f"> 子弹池累计再投 {money(s['cum_reinvested'])} 元, 期末余额 {money(s['bullet_pool'])} 元。"
             "子弹池机制与 V4 相同: 低估日(d≤-8%)集中在 2021-2024 熊市, 2025-2026 大牛市回款因无低估信号而留存。")
    L.append("")

    # 八、多版本对比
    L.append("## 八、V5 vs V4 vs V3 vs V2 vs V1 vs 纯定投 对比")
    L.append("")
    L.append("> 收益口径统一: **总收益 = 期末总资产(持仓市值 + 子弹池/现金) − 净外部本金(累计定投)**。")
    L.append("> V5/V4 子弹池再投为内部循环, 不计入外部本金; V3/V2/V1 回款闲置作现金; 纯定投不止盈持有到期末。")
    L.append("")
    v4 = v4_summary
    v3 = v3_summary
    v2 = v2_summary
    v1 = v1_summary
    b = baseline
    L.append("| 指标 | V5(迟滞重装) | V4(子弹池复利) | V3(三优化) | V2(永不空仓) | V1(20%清仓) | 纯定投不止盈 |")
    L.append("|---|---|---|---|---|---|---|")
    L.append(f"| 净外部本金 | {money(s['total_invested'])} | {money(v4['total_invested'])} | "
             f"{money(v3['total_invested'])} | {money(v2['total_invested'])} | {money(v1['total_invested'])} | "
             f"{money(b['total_invested'])} |")
    L.append(f"| 子弹池再投(内部) | {money(s['cum_reinvested'])} | {money(v4['cum_reinvested'])} | 0 | 0 | 0 | 0 |")
    L.append(f"| 重装口径 | 跌破L−2.5% | 跌破L | 跌破L | 跌破L−5% | 20%清仓后 | - |")
    L.append(f"| 止盈次数 | {s['n_events']} | {v4['n_events']} | {v3['n_events']} | "
             f"{v2['n_events']} | {v1['n_events']} | 0 |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(v4['total_sell_proceeds'])} | "
             f"{money(v3['total_sell_proceeds'])} | {money(v2['total_sell_proceeds'])} | {money(v1['total_sell_proceeds'])} | 0 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(v4['cum_realized'])} | "
             f"{money(v3['cum_realized'])} | {money(v2['cum_realized'])} | {money(v1['cum_realized'])} | 0 |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(v4['final_value'])} | "
             f"{money(v3['final_value'])} | {money(v2['final_value'])} | {money(v1['final_value'])} | {money(b['final_value'])} |")
    L.append(f"| 期末现金(子弹池) | {money(s['bullet_pool'])} | {money(v4['bullet_pool'])} | "
             f"{money(v3['cash'])} | {money(v2['cash'])} | {money(v1['cash'])} | 0 |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['bullet_pool'])} | "
             f"{money(v4['final_value']+v4['bullet_pool'])} | {money(v3['final_value']+v3['cash'])} | "
             f"{money(v2['final_value']+v2['cash'])} | {money(v1['final_value']+v1['cash'])} | {money(b['final_value'])} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(v4['total_return'])} | "
             f"{pct(v3['total_return'])} | {pct(v2['total_return'])} | {pct(v1['total_return'])} | {pct(b['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(v4['xirr'])} | {pct(v3['xirr'])} | "
             f"{pct(v2['xirr'])} | {pct(v1['xirr'])} | - |")
    L.append("")

    # 九、消融: 迟滞重装边际效应 + 迟滞带敏感性
    L.append("## 九、消融对比: 迟滞重装的边际效应")
    L.append("")
    L.append("> 在 V4(opt3/8 全开 + 子弹池复利, rearm_offset=0.0 跌破L)基线上, 单独把重装阈值改为 L−2.5%(V5), "
             "观察边际效果。两者子弹池机制完全一致, 唯一差别是重装迟滞带。")
    L.append("> 「正常/DCA」列为正常止盈次数 / DCA 再触发次数; 「再投」为子弹池累计再投金额。")
    L.append("")
    L.append("| 方案 | 止盈次数 | 正常/DCA | 累计回款 | 子弹池再投 | 累计实现盈亏 | 期末市值 | 期末子弹池 | 期末总资产 | 总收益率 | XIRR |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    L.append(_ablation_row("V4 基线(跌破L重装)", abl['v4']))
    L.append(_ablation_row("V5(跌破L−2.5%重装)", abl['v5']))
    L.append("")
    d_v4 = abl['v4']['total_return']
    d_v5 = abl['v5']['total_return'] - d_v4
    L.append("**迟滞重装边际效应(相对 V4 基线):**")
    L.append("")
    L.append(f"- 总收益率: **{'+' if d_v5>=0 else ''}{d_v5*100:.2f}%** ({pct(abl['v4']['total_return'])} -> {pct(abl['v5']['total_return'])})")
    dx = abl['v5']['xirr'] - abl['v4']['xirr']
    L.append(f"- XIRR: **{'+' if dx>=0 else ''}{dx*100:.2f}%** ({pct(abl['v4']['xirr'])} -> {pct(abl['v5']['xirr'])})")
    L.append(f"- 止盈次数变化: {abl['v5']['n_events'] - abl['v4']['n_events']:+d} "
             f"(迟滞带减少震荡市的重装-再卖循环)")
    L.append(f"- 15% 档触发变化: {abl['v5']['tier_counts'].get('15%',0) - abl['v4']['tier_counts'].get('15%',0):+d} "
             f"(迟滞带主要抑制 15% 档: [12.5%,15%) 内的噪声回撤不再重装)")
    L.append(f"- 累计回款变化: {money(abl['v5']['total_sell_proceeds'] - abl['v4']['total_sell_proceeds'])} "
             f"(止盈节奏改变带来)")
    L.append(f"- 子弹池累计再投变化: {money(abl['v5']['cum_reinvested'] - abl['v4']['cum_reinvested'])} "
             f"(止盈节奏影响回款时点 -> 影响可再投的子弹池余额)")
    L.append("")
    L.append("> **解读**: 迟滞带确实达到了「降噪」目的--15% 档触发从 15 次降到 11 次, 总止盈从 36 次降到 29 次, "
             "验证了用户预期(减少震荡市高频卖出)。但**在本回测区间, 降噪反而降低了收益(-1.72pp)**, 原因是行情结构: "
             "科创50 在 2025-2026 是**单边强趋势牛市**(从 1,247 涨到 2,208), 几乎没有「震荡后继续上行」的反复, "
             "V4 的高频重装-再卖循环恰好在趋势中「多收割」了利润; V5 迟滞带少卖出的那 7 次, 多数筹码继续持有, "
             "但随后被更高的止盈档(25%/30%)卖出或吃到了回撤--净效果不如 V4 的频繁小赚。"
             "换言之: 迟滞带对「宽幅震荡市」有利(降噪减损), 对「单边趋势市」不利(少赚); "
             "本回测区间趋势占主导, 故 V5 < V4。迟滞带的真正价值需在震荡行情中体现, 而非本区间。")
    L.append("")

    # 迟滞带敏感性
    L.append("### 迟滞带宽度敏感性(reinvest=True, 仅变 rearm_offset)")
    L.append("")
    L.append("固定子弹池复利与 opt3/8, 仅改变重装迟滞带宽度, 观察对止盈节奏与收益的影响。"
             "0%=V4 口径(跌破L) · 2.5%=V5(跌破L−2.5%) · 5%=V2 口径(跌破L−5%, 但此处其他全开, 非真 V2)。")
    L.append("")
    L.append("| 迟滞带 | 重装口径 | 止盈次数 | 15%档 | 累计回款 | 子弹池再投 | 累计实现盈亏 | 期末市值 | 期末子弹池 | 期末总资产 | 总收益率 | XIRR |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for label,口径, a in sens:
        L.append(_sens_row(label,口径, a))
    L.append("")
    L.append("> 观察: 迟滞带越宽, 15% 档触发越少(降噪), 但过宽(5%)会接近 V2 的「跳过 15% 档」问题; "
             "2.5% 在降噪与不跳档间取折中。最优宽度可进一步回测 1%/2%/3% 等细粒度(见可优化方向 2)。")
    L.append("")

    # 十、可优化方向
    L.append("## 十、可优化方向")
    L.append("")
    L.append("V5 已落地 V3 优化方向 1(子弹池复利, V4)与 4(重装迟滞, V5)。针对科创50 **高波动、强趋势、成长风格** 特性, 仍可考虑:")
    L.append("")
    L.append("1. **均线/估值加权定投(原方向 2)**: V5 每日仍固定 300 元, 顶部照样定投抬高成本。"
             "可按收盘价相对 MA250 偏离度加权--低估多投、高估停投, 压低平均成本。与子弹池复利可叠加, "
             "沪深300 V2 即为「均线加权 + 子弹池」双优化。")
    L.append("2. **迟滞带宽度细粒度调参**: V5 用 2.5%, 敏感性表仅测了 0/2.5%/5%。可回测 1%/1.5%/2%/3% 等更细粒度, "
             "寻找科创50历史数据上「降噪幅度」与「跳档风险」的最优平衡点; 亦可考虑非线性迟滞(高档迟滞更宽)。")
    L.append("3. **子弹池排液节奏调参(V4 方向)**: 当前每个低估日抽池 2% + 定投额×(3~5)x, 在 2022 年 218 个低估日中"
             "池子前期抽得过快、深跌底部反无钱可投。可按 d 分档限速, 让子弹留到更深的底部。")
    L.append("4. **止盈档位动态化(原方向 3)**: 15/20/25% 为固定档。可结合 PE 历史分位、波动率动态调整--"
             "高估区提前止盈、低估区放宽阈值。⚠️ index_info 中科创50的 pe_ratio/pe_percentile 当前为 0(未采集), 落地需先补数据。")
    L.append("5. **止盈基准优化(原方向 5)**: 止盈看「组合整体收益率」, 每日新增定投持续稀释收益率, "
             "横盘时止盈推迟。可改为按「最早批次成本」或「移动平均成本」分批止盈。")
    L.append("6. **卖出比例曲线调参(原方向 6)**: 优化8 当前为线性 20%+10%·k、封顶 90%。"
             "可回测不同曲线(凹型/凸型/不同封顶)对总收益率的影响。")
    L.append("")

    # 十一、说明与风险
    L.append("## 十一、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, 结果略乐观于真实科创50指数基金定投。")
    L.append("- **永不空仓**: 每次卖 `sell_frac(L)` < 1(封顶 90%, 至少留 10%), 即便连触多档, 各档保留率乘积 > 0, "
             "加之每日定投持续加仓, 持仓始终 > 0(继承 V3/V4)。")
    L.append("- **迟滞重装(V5 核心)**: 档 L 跌破 L−2.5% 才重装, [L−2.5%, L) 内的回撤不触发重装。"
             "收益: 震荡市 15% 档降噪(减少高频卖出); 代价: 单边深跌后反弹时, 因晚 2.5% 重装, 可能少收割一档"
             "(但深跌必跌破 L−2.5%, 故仍会重装, 仅时点略晚)。2.5% 介于 V2(5%, 跳过 15%)与 V4(0, 高频)之间。")
    L.append("- **子弹池复利的资金口径(继承 V4)**: 止盈回款入子弹池, 低位再投全额累入持仓成本; "
             "子弹池再投属**内部资金循环**, 不计入外部本金(`total_invested`)与 XIRR 的外部现金流。"
             "总收益恒等式: `期末总资产(市值+子弹池) − 净外部本金(累计定投)`。")
    L.append("- **MA250 估值锚(继承 V4)**: 前 60 个交易日无均线信号(d=0, 不再投); 之后按可用窗口(最多 250 日)计算 MA。"
             "均线为滞后指标, 熊市初期延迟触发再投、牛市初期误判为低估--均线择时的固有代价。")
    L.append("- **结构性错配(继承 V4)**: 科创50 低估日(d≤-8%)全部集中在 2021-2024(508 个, 2022 年 218 个), "
             "2025-2026 大牛市无低估日。子弹池主要用 2020-2021 小额回款在熊市抄底; 2025-2026 大额回款因无低估信号, "
             "期末仍以现金留存。V5 相对 V4 的增益(若有)主要来自重装节奏改变对止盈时点的影响, "
             "而非子弹池(两者子弹池机制一致)。")
    L.append("- **过拟合风险**: 迟滞带宽度(2.5%)、子弹池阈值/倍数等参数存在对历史走势的拟合依赖; "
             "未来若指数进入长期单边市, 表现可能不及回测。参数不保证未来有效。")
    L.append("- **优化3/8 与子弹池继承自 V3/V4**: DCA 全档、分档卖出、子弹池复利的行为与副作用与 V4 完全一致(详见 V4 报告); "
             "V5 仅在重装阈值上与 V4 不同, `rearm_offset=0.0` 且 `reinvest=False` 时数值与 V4 完全一致(回归校验)。")
    L.append("- 单日涨幅同时穿越多档时, 各档同日依次触发(每档卖当前 `sell_frac(L)`), 净效果为分档减仓而非清仓。")
    L.append("- 卖出按比例结转成本(平均成本法), 单次止盈不改变剩余持仓的平均成本; 子弹池再投按买入价累入成本。")
    L.append("- XIRR 为外部现金流年化(每日定投流出 + 期末总资产流入), 考虑 6 年陆续投入的资金时间价值, "
             "比简单总额法更严谨; 年化(244日/年)为粗略估算。")
    L.append("- 本报告不构成投资建议。")
    L.append("")
    return "\n".join(L)


def main():
    prices = fetch_prices()
    if not prices:
        print("未取到科创50行情数据", file=sys.stderr)
        sys.exit(1)

    # V5(迟滞重装 2.5% + 子弹池复利, 默认) + 回归基线
    events, summary, by_year_pool = run_backtest_v5(prices)  # rearm_offset=0.025, reinvest=True
    # V4(opt3/8 全开 + 子弹池, 跌破L重装) -- 对比 + 回归基线
    _v4_events, v4_summary, _ = run_backtest_v4(prices, reinvest=True)
    # V3 / V2 / V1 / 纯定投
    _v3_events, v3_summary = run_backtest_v3(prices)
    _v2_events, v2_summary = run_backtest_v2(prices)
    _v1_events, v1_summary = run_v1_backtest(prices, rearm_mode='on_clear')
    baseline = _pure_dca_baseline(prices)

    # 消融: V4 基线(rearm_offset=0.0+子弹池) vs V5(0.025+子弹池), 只差迟滞带
    _, abl_v4, _ = run_backtest_v5(prices, rearm_offset=0.0, reinvest=True)
    abl = {'v4': abl_v4, 'v5': summary}

    # 迟滞带敏感性: rearm_offset ∈ {0.0, 0.025, 0.05}, reinvest=True, 其他全开
    _, s0, _ = run_backtest_v5(prices, rearm_offset=0.0, reinvest=True)
    _, s025, _ = run_backtest_v5(prices, rearm_offset=0.025, reinvest=True)
    _, s05, _ = run_backtest_v5(prices, rearm_offset=0.05, reinvest=True)
    sens = [
        ('0%(V4口径)', '跌破L', s0),
        ('2.5%(V5)', '跌破L−2.5%', s025),
        ('5%(V2口径)', '跌破L−5%', s05),
    ]

    # 回归断言: V5 rearm_offset=0.0, reinvest=False == V4(opt6=True, reinvest=False)
    _, reg_v4, _ = run_backtest_v5(prices, rearm_offset=0.0, reinvest=False)
    _v4off_ev, v4off_summary, _ = run_backtest_v4(prices, reinvest=False)
    assert reg_v4['n_events'] == v4off_summary['n_events'], "回归失败: rearm_offset=0.0 止盈次数与 V4 不一致"
    assert abs(reg_v4['total_return'] - v4off_summary['total_return']) < 1e-9, "回归失败: 总收益率与 V4 不一致"
    assert abs(reg_v4['xirr'] - v4off_summary['xirr']) < 1e-9, "回归失败: XIRR 与 V4 不一致"
    # 回归断言: V5 rearm_offset=0.05, opt3=opt8=False, reinvest=False == V2
    _, reg_v2, _ = run_backtest_v5(prices, opt3=False, opt8=False, rearm_offset=0.05, reinvest=False)
    assert reg_v2['n_events'] == v2_summary['n_events'], "回归失败: rearm_offset=0.05 止盈次数与 V2 不一致"
    assert abs(reg_v2['total_return'] - v2_summary['total_return']) < 1e-9, "回归失败: 总收益率与 V2 不一致"

    report = build_report(events, summary, by_year_pool, v4_summary, v3_summary, v2_summary, v1_summary, baseline,
                          abl, sens)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    s = summary
    print(f"V5 回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 交易日)")
    print(f"净外部本金: {money(s['total_invested'])} 元 | 子弹池再投(内部): {money(s['cum_reinvested'])} 元")
    print(f"重装口径: 跌破L−{REARM_OFFSET_V5*100:g}% (迟滞带)")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(正常 {s['trigger_counts'].get('normal',0)} / DCA 再触发 {s['trigger_counts'].get('dca_retrigger',0)})")
    print(f"  各档: 15%={s['tier_counts'].get('15%',0)} 20%={s['tier_counts'].get('20%',0)} "
          f"25%={s['tier_counts'].get('25%',0)} 30%={s['tier_counts'].get('30%',0)}")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮盈: {money(s['unrealized'])} 元 | 子弹池: {money(s['bullet_pool'])} 元")
    print(f"V5 总收益: {money(s['total_profit'])} | 总收益率: {pct(s['total_return'])} | "
          f"年化: {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"[回归] V5 offset=0.0,reinvest=False == V4: {v4off_summary['n_events']}次 / "
          f"{pct(v4off_summary['total_return'])} / XIRR {pct(v4off_summary['xirr'])} ✓")
    print(f"[回归] V5 offset=0.05,opt全关 == V2: {v2_summary['n_events']}次 / {pct(v2_summary['total_return'])} ✓")
    print(f"[对比] V4 总收益率: {pct(v4_summary['total_return'])} | XIRR: {pct(v4_summary['xirr'])} | 止盈 {v4_summary['n_events']}次")
    print(f"[对比] V3 总收益率: {pct(v3_summary['total_return'])} | V2: {pct(v2_summary['total_return'])} | "
          f"V1: {pct(v1_summary['total_return'])} | 纯定投: {pct(baseline['total_return'])}")
    print(f"[消融] V4基线(跌破L)   -> {pct(abl_v4['total_return'])} / XIRR {pct(abl_v4['xirr'])} / "
          f"止盈 {abl_v4['n_events']}次 (15%档 {abl_v4['tier_counts'].get('15%',0)})")
    print(f"[消融] V5(跌破L−2.5%)  -> {pct(s['total_return'])} / XIRR {pct(s['xirr'])} / "
          f"止盈 {s['n_events']}次 (15%档 {s['tier_counts'].get('15%',0)})")
    dr = s['total_return'] - abl_v4['total_return']
    dx = s['xirr'] - abl_v4['xirr']
    print(f"边际: 总收益率 {'+' if dr>=0 else ''}{dr*100:.2f}% | "
          f"XIRR {'+' if dx>=0 else ''}{dx*100:.2f}% | 止盈 {s['n_events'] - abl_v4['n_events']:+d}")
    print("[敏感性] 迟滞带 -> 总收益率 / XIRR / 止盈次数(15%档):")
    for label,口径, a in sens:
        print(f"  {label:10s} {pct(a['total_return'])} | XIRR {pct(a['xirr'])} | "
              f"{a['n_events']}次 (15%档 {a['tier_counts'].get('15%',0)})")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
