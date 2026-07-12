#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯止盈(永不空仓) + 子弹池复利 回测 V4

相对 V3(`backtest_kc50_dca_v3.py`)的核心优化(原 V3 优化方向 1 -- 回款再投/子弹池复利):
  止盈回款不再闲置, 进入子弹池; 当收盘价低于 250 日均线 8% 以上(d ≤ -8%)时,
  从子弹池取钱加速抄底(-8%~-20% 加速 3 倍、≤-20% 加速 5 倍), 把高位套现的钱变成
  低位筹码, 实现复利。沪深300 V2 已验证此优化可显著提升总收益。

  ⚠️ V4 仅叠加「子弹池复利」(优化1), 不引入「均线/估值加权定投」(优化2) -- 每日仍固定
  300 元定投, 外部本金与 V3 完全一致, 净增量仅来自回款的内部循环再投。这样 V4 vs V3
  是「同本金、不同资金周转」的干净对照。

引擎参数化(reinvest 开关 + 复用 V3 的 opt3/opt6/opt8):
  - reinvest=False 精确复现 V3(回归校验); 再加 opt 全关 复现 V2。
  - reinvest=True 即 V4(子弹池复利)。

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

# 复用 V1 的数据访问与格式化辅助(经 V3 再导出亦可, 这里直接从 V1 取)
from tasks.backtest_kc50_dca import (  # noqa: E402
    fetch_prices, _xirr, money, shares, pct,
    DAILY_INVEST, TRADING_DAYS_PER_YEAR, run_backtest as run_v1_backtest,
)
# 复用 V2/V3 用于回归校验与对比
from tasks.backtest_kc50_dca_v2 import run_backtest_v2  # noqa: E402
from tasks.backtest_kc50_dca_v3 import (  # noqa: E402
    run_backtest_v3, sell_frac, _tier_label, _tier_index,
    FIRST_TIER, TIER_STEP, MAX_TIER, TIERS,
    SELL_FRAC_BASE, SELL_FRAC_STEP, SELL_FRAC_CAP,
    _pure_dca_baseline, _sell_frac_table,
)

# ---- 子弹池复利参数(与沪深300 V2 同款, 估值锚用 MA250) ----
MA_WINDOW = 250                # 250 日简单均线(估值锚)
MA_WARMUP = 60                 # 不足 60 日无均线信号(d=0, 不触发再投); 与沪深300 V2 一致
REINVEST_D_THRESHOLD = -0.08   # d ≤ -8% 启动子弹池低位再投
REINVEST_MULT = 3.0            # -8% ~ -20% 加速 3 倍
REINVEST_MULT_DEEP = 5.0       # d ≤ -20% 加速 5 倍
POOL_DRAIN_FRAC = 0.02         # 每个低估日另抽子弹池余额的 2% 加速消化

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告_V4.md'
)


def _reinvest_mult(d):
    """子弹池再投加速倍数: d≤-20%->5x · -20%<d≤-8%->3x · d>-8%->0(不触发)。"""
    if d <= -0.20:
        return REINVEST_MULT_DEEP
    if d <= REINVEST_D_THRESHOLD:
        return REINVEST_MULT
    return 0.0


def _reinvest_target(pool, dca_amount, d):
    """单日子弹池再投目标额 = 池余额×POOL_DRAIN_FRAC + 当日定投额×加速倍数。
    实际再投额 = min(pool, target), 保证池不过零。"""
    return pool * POOL_DRAIN_FRAC + dca_amount * _reinvest_mult(d)


def run_backtest_v4(prices, opt3=True, opt6=True, opt8=True, reinvest=True):
    """执行 V4 回测, 返回 (events, summary, by_year_pool)。

    opt3: DCA 再触发推广到所有档位(True) / 仅 15%(False, V2)
    opt6: 重装阈值 = 跌破 L(True) / 跌破 L−5%(False, V2)
    opt8: 卖出比例随档位递增(True) / 固定 30%(False, V2)
    reinvest: 止盈回款入子弹池并在低位(d≤-8%)加速再投(True, V4) / 回款闲置(False, 退回 V3)
    reinvest=False 精确复现 V3; 再加 opt 全关 复现 V2。
    """
    armed = {L: True for L in TIERS}      # 各档是否装填
    total_shares = 0.0                    # 当前持仓份额
    total_cost = 0.0                      # 当前持仓成本(卖出按比例结转; 子弹池再投累入)
    total_invested = 0.0                  # 累计定投金额(外部本金, 与 V3 一致)
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
        bullet_pool += sell_proceeds           # 回款入子弹池(V3 是 idle cash)
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

        # 1) 每日定投买入(固定 300, 与 V3 一致 -- 不引入均线加权定投)
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

        # 3) 持仓收益率(子弹池再投会压低成本 -> 抬高收益率, 影响后续止盈触发)
        profit_rate = (total_shares * price - total_cost) / total_cost if total_cost > 0 else 0.0
        if profit_rate > peak_profit_rate:
            peak_profit_rate = profit_rate

        # 4) 重装: 档位 L 已触发 且 收益率跌破重装阈值 -> 重装
        #    优化6: 阈值 = L(跌破自身档位); V2: 阈值 = L−5%
        for L in TIERS:
            if not armed[L]:
                rearm_threshold = L if opt6 else L - TIER_STEP
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
    # 净外部本金 = 仅累计定投; 子弹池再投是内部资金循环(来自止盈回款), 不计入本金
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
        'total_invested': total_invested,          # 外部本金(与 V3 一致)
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
        'cash': bullet_pool,                       # 别名(与 V3 口径对齐: 期末现金)
        'total_profit': total_profit,
        'total_return': total_return,
        'annualized': annualized,
        'peak_profit_rate': peak_profit_rate,
        'xirr': xirr_val,
        'opt3': opt3, 'opt6': opt6, 'opt8': opt8, 'reinvest': reinvest,
    }
    return events, summary, dict(by_year_pool)


def _ablation_row(label, s):
    return (f"| {label} | {s['n_events']} | "
            f"{s['trigger_counts'].get('normal', 0)}/{s['trigger_counts'].get('dca_retrigger', 0)} | "
            f"{money(s['total_sell_proceeds'])} | {money(s.get('cum_reinvested', 0.0))} | "
            f"{money(s['cum_realized'])} | {money(s['final_value'])} | "
            f"{money(s['bullet_pool'])} | {money(s['final_value'] + s['bullet_pool'])} | "
            f"{pct(s['total_return'])} | {pct(s['xirr'])} |")


def build_report(events, summary, by_year_pool, v3_summary, v2_summary, v1_summary, baseline, abl):
    """生成 V4 报告。

    abl = {'v3':s(V3 基线, reinvest=False), 'v4':s(V4, reinvest=True)} 子弹池消融汇总。
    """
    L = []
    s = summary
    L.append("# 科创50 定投止盈回测 V4(永不空仓 + 子弹池复利)")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca_v4.py`。")
    L.append("> 本报告为 V3(`科创50_定投止盈_回测报告_V3.md`)的策略升级版, 落地 V3 优化方向 1(回款再投/子弹池复利)。")
    L.append("")

    # 一、策略变更
    L.append("## 一、V4 相对 V3 的策略变更")
    L.append("")
    L.append("| 维度 | V3 | V4 |")
    L.append("|---|---|---|")
    L.append("| 回款处理 | 止盈回款留作**闲置现金**, 零复利 | **回款入子弹池**, 低位(d≤-8%)加速抄底, 复利再投 |")
    L.append("| 估值锚 | 无 | **250 日均线(MA250)**: 收盘价低于均线 8% 以上启动再投 |")
    L.append("| 低位再投 | 无 | d≤-8%: 每日抽池 2% + 当日定投额×加速倍数; -8%~-20% 加速 **3 倍**、≤-20% 加速 **5 倍** |")
    L.append("| 每日定投 | 固定 300 元 | **固定 300 元(不变)** -- 仅叠加子弹池, 不引入均线加权定投 |")
    L.append("| 外部本金 | 468,900 元 | **468,900 元(一致)** -- 净增量仅来自回款内部循环 |")
    L.append("| 止盈/重装/DCA | opt3/6/8 三项优化(继承 V3) | **完全继承 V3**, 不改动 |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("V3 把止盈回款(累计 58 万)全部留作闲置现金, 零复利, 是 V3 报告点名的「最大优化杠杆」。"
             "V4 在 V3 的「永不空仓 + DCA 全档 + 跌破重装 + 分档卖出」之上, **仅叠加**一项优化--"
             "**回款再投(子弹池复利)**: 止盈回款不再闲置, 进入子弹池; 当收盘价低于 250 日均线 8% 以上"
             "(d ≤ -8%, 估值偏低)时, 从子弹池取钱加速抄底, 把高位套现的钱变成低位筹码。"
             "这与沪深300 V2(`backtest_hs300_dca_v2.py`)的子弹池机制同款, 已在沪深300 上验证可显著提升总收益。")
    L.append("")
    L.append("为做**干净对照**, V4 刻意**不**引入「均线/估值加权定投」(V3 优化方向 2): 每日仍固定 300 元定投, "
             "外部本金与 V3 完全一致(468,900 元)。因此 V4 vs V3 是「同本金、不同资金周转」的对比--"
             "V4 的全部净增量来自回款的内部循环再投, 而非追加本金。子弹池再投属内部资金循环(来自止盈回款), "
             "不计入外部本金, 也不计入 XIRR 的外部现金流。")
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
    L.append("| 重装规则(优化6) | 档位 L 在收益率跌破 L 时重装(15%:跌破15% · 20%:跌破20%…) |")
    L.append(f"| 均线(估值锚) | {MA_WINDOW} 日简单均线(MA{MA_WINDOW}); 不足 {MA_WARMUP} 日无信号(d=0, 不触发再投), "
             f"之后按可用窗口(最多 {MA_WINDOW} 日)计算 -- 与沪深300 V2 一致 |")
    L.append(f"| 子弹池再投(优化1) | d≤{int(REINVEST_D_THRESHOLD*100)}% 启动; 每日再投目标 = 池余额×{int(POOL_DRAIN_FRAC*100)}% "
             f"+ 当日定投额×加速倍数, 实际再投 min(池余额, 目标); "
             f"-8%~-20% 加速 {int(REINVEST_MULT)}x、≤-20% 加速 {int(REINVEST_MULT_DEEP)}x |")
    L.append("| 持仓收益率 | (持仓市值 − 持仓成本) / 持仓成本; 子弹池低位再投会压低成本、抬高收益率 |")
    L.append("| 成本结转 | 卖出按比例结转成本(平均成本法); 子弹池再投额按买入价累入成本 |")
    L.append("| 每日顺序 | 先定投买入, 再子弹池低位再投, 再判定止盈(重装 -> 正常止盈 -> DCA 再触发) |")
    L.append("| 回款处理 | 止盈回款**入子弹池**(不再闲置); 低位再投消耗子弹池; 期末余额作现金 |")
    L.append("| 费用 | 不计交易费用、分红再投、税收; 指数点位近似可投资(可买碎额) |")
    L.append("")
    L.append("### 优化8 卖出比例表(继承 V3)")
    L.append("")
    L.append("| 档位 | 卖出比例 | 留存比例 |")
    L.append("|---|---|---|")
    for label, frac in _sell_frac_table():
        L.append(f"| {label} | {int(round(frac * 100))}% | {int(round((1 - frac) * 100))}% |")
    L.append(f"| ≥50% | {int(SELL_FRAC_CAP * 100)}%(封顶) | {int(round((1 - SELL_FRAC_CAP) * 100))}% |")
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

    # 七、子弹池运作(按年)- 复利核心
    L.append("## 七、子弹池运作(按年)- 复利核心")
    L.append("")
    L.append("子弹池 = 止盈回款累积的现金; 低估日(d ≤ -8%)从池中取钱加速抄底。"
             "下表展示每年**流入(止盈回款)-> 流出(低位再投)-> 年末余额**。")
    L.append("")
    L.append("| 年份 | 流入(止盈回款) | 流出(低位再投) | 年末子弹池余额 |")
    L.append("|---|---|---|---|")
    for y in sorted(by_year_pool):
        p = by_year_pool[y]
        L.append(f"| {y} | {money(p['inflow'])} | {money(p['outflow'])} | {money(p['end'])} |")
    L.append("")
    L.append(f"> 子弹池累计再投 {money(s['cum_reinvested'])} 元, 期末余额 {money(s['bullet_pool'])} 元。"
             "观察: 科创50 的低估日(d≤-8%)集中在 2021-2024 熊市(2022 年尤甚), 故子弹池主要在该区间流出抄底; "
             "2025-2026 大牛市止盈回款大量入池, 但因后续已无低估信号, 期末子弹池保留较多现金(见说明与风险)。")
    L.append("")

    # 八、V4 vs V3 vs V2 vs V1 vs 纯定投 对比
    L.append("## 八、V4 vs V3 vs V2 vs V1 vs 纯定投 对比")
    L.append("")
    L.append("> 收益口径统一: **总收益 = 期末总资产(持仓市值 + 子弹池/现金) − 净外部本金(累计定投)**。")
    L.append("> V4 子弹池再投为内部循环, 不计入外部本金; V3/V2/V1 回款闲置作现金; 纯定投不止盈持有到期末。")
    L.append("")
    v3 = v3_summary
    v2 = v2_summary
    v1 = v1_summary
    b = baseline
    L.append("| 指标 | V4(子弹池复利) | V3(三优化) | V2(永不空仓) | V1(20%清仓) | 纯定投不止盈 |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| 净外部本金 | {money(s['total_invested'])} | {money(v3['total_invested'])} | "
             f"{money(v2['total_invested'])} | {money(v1['total_invested'])} | {money(b['total_invested'])} |")
    L.append(f"| 子弹池再投(内部) | {money(s['cum_reinvested'])} | 0 | 0 | 0 | 0 |")
    L.append(f"| 止盈次数 | {s['n_events']} | {v3['n_events']} | {v2['n_events']} | {v1['n_events']} | 0 |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(v3['total_sell_proceeds'])} | "
             f"{money(v2['total_sell_proceeds'])} | {money(v1['total_sell_proceeds'])} | 0 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(v3['cum_realized'])} | "
             f"{money(v2['cum_realized'])} | {money(v1['cum_realized'])} | 0 |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(v3['final_value'])} | "
             f"{money(v2['final_value'])} | {money(v1['final_value'])} | {money(b['final_value'])} |")
    L.append(f"| 期末现金(子弹池) | {money(s['bullet_pool'])} | {money(v3['cash'])} | "
             f"{money(v2['cash'])} | {money(v1['cash'])} | 0 |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['bullet_pool'])} | "
             f"{money(v3['final_value']+v3['cash'])} | {money(v2['final_value']+v2['cash'])} | "
             f"{money(v1['final_value']+v1['cash'])} | {money(b['final_value'])} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(v3['total_return'])} | "
             f"{pct(v2['total_return'])} | {pct(v1['total_return'])} | {pct(b['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(v3['xirr'])} | {pct(v2['xirr'])} | "
             f"{pct(v1['xirr'])} | - |")
    L.append("")

    # 九、消融对比(V4 = V3 + 子弹池)
    L.append("## 九、消融对比: 子弹池复利的边际效应")
    L.append("")
    L.append("> 在 V3(opt3/6/8 全开)基线上, 单独开启子弹池复利(reinvest), 观察边际效果。")
    L.append("> 「正常/DCA」列为正常止盈次数 / DCA 再触发次数; 「再投」为子弹池累计再投金额。")
    L.append("")
    L.append("| 方案 | 止盈次数 | 正常/DCA | 累计回款 | 子弹池再投 | 累计实现盈亏 | 期末市值 | 期末子弹池 | 期末总资产 | 总收益率 | XIRR |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    L.append(_ablation_row("V3 基线(回款闲置)", abl['v3']))
    L.append(_ablation_row("V4(子弹池复利)", abl['v4']))
    L.append("")
    d_v3 = abl['v3']['total_return']
    d_v4 = abl['v4']['total_return'] - d_v3
    L.append("**子弹池复利边际效应(相对 V3 基线):**")
    L.append("")
    L.append(f"- 总收益率: **+{pct(d_v4)}** ({pct(abl['v3']['total_return'])} -> {pct(abl['v4']['total_return'])})")
    L.append(f"- XIRR: **+{pct(abl['v4']['xirr'] - abl['v3']['xirr'])}** ({pct(abl['v3']['xirr'])} -> {pct(abl['v4']['xirr'])})")
    extra_proceeds = abl['v4']['total_sell_proceeds'] - abl['v3']['total_sell_proceeds']
    L.append(f"- 累计回款变化: {money(extra_proceeds)} (低位再投压低成本→收益率抬高→多触发 {abl['v4']['n_events'] - abl['v3']['n_events']:+d} 次止盈, 卖出更多份额)")
    L.append(f"- 子弹池累计再投: {money(abl['v4']['cum_reinvested'])} 元 (于 2021-2024 熊市低位 d≤-8% 消耗, 见第七节)")
    L.append(f"- 期末市值变化: {money(abl['v4']['final_value'] - abl['v3']['final_value'])} "
             f"(多止盈使期末持仓更轻; 低位再投的筹码多数已在 2025-2026 止盈兑现而非持有到期末)")
    L.append(f"- 期末子弹池变化: {money(abl['v4']['bullet_pool'] - abl['v3']['bullet_pool'])} "
             f"(多止盈带来回款 +{extra_proceeds/10000:.1f} 万、再投 −{abl['v4']['cum_reinvested']/10000:.1f} 万, 净增; "
             f"2025-2026 无低估日, 增量回款无法再投而留存)")
    L.append("")
    L.append("> **解读**: 子弹池把 V3 闲置的高位回款, 在 2021-2024 熊市低位(d≤-8%)转化为筹码, "
             "形成「涨时兑现、跌时建仓」的复利循环。因 V4 不追加本金, 净增量全部来自回款的内部周转。"
             "需注意: 低位再投压低了平均成本, 使 2025-2026 止盈更易触发(止盈次数 31->36), "
             "部分低位筹码在 2025-08 行情启动初期(1,247~1,364 点)即被止盈兑现, 未能吃到后续涨至 2,208(区间最高)的完整涨幅; "
             "加之 2025-2026 回款已无低估日可再投、多数闲置, 故 V4 增益(+6.14pp)虽显著但非爆发式--"
             "这是科创50「熊市集中、牛市尾段」的行情结构叠加止盈节奏共同决定的(详见第十一节结构性错配)。")
    L.append("")

    # 十、可优化方向
    L.append("## 十、可优化方向")
    L.append("")
    L.append("V4 已落地 V3 优化方向 1(子弹池复利)。针对科创50 **高波动、强趋势、成长风格** 特性, 仍可考虑:")
    L.append("")
    L.append("1. **均线/估值加权定投(原方向 2)**: V4 每日仍固定 300 元, 顶部照样定投抬高成本。"
             "可按收盘价相对 MA250 偏离度加权--低估多投、高估停投, 压低平均成本。与子弹池复利可叠加, "
             "沪深300 V2 即为「均线加权 + 子弹池」双优化。")
    L.append("2. **子弹池排液节奏调参**: 当前每个低估日抽池 2% + 定投额×(3~5)x, 在 2022 年长达 218 个低估日中"
             "池子前期抽得过快、集中在熊市上半场(价格尚未跌透), 深跌底部(如 2022-04 -35.9%)反而池已近空。"
             "可改为更平缓的排液曲线, 或按 d 分档限速(d 越深、单日占比越低但持续更久), 让子弹留到更深的底部。")
    L.append("3. **止盈档位动态化(原方向 3)**: 15/20/25% 为固定档。可结合 PE 历史分位、波动率动态调整--"
             "高估区提前止盈、低估区放宽阈值。⚠️ index_info 中科创50的 pe_ratio/pe_percentile 当前为 0(未采集), "
             "落地需先补数据。")
    L.append("4. **重装冷却/迟滞(原方向 4)**: 优化6 推广到全档后, 小幅回撤即重装可能造成 15% 档高频触发。"
             "可给重装加冷却期或迟滞带, 减少噪声触发的过早减仓。")
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
             "加之每日定投持续加仓, 持仓始终 > 0(继承 V3)。")
    L.append("- **子弹池复利的资金口径**: 止盈回款入子弹池(含收回的成本与实现盈亏), 低位再投时全额累入持仓成本; "
             "子弹池再投属**内部资金循环**, 不计入外部本金(`total_invested`)与 XIRR 的外部现金流。"
             "总收益恒等式: `期末总资产(市值+子弹池) − 净外部本金(累计定投)`。")
    L.append("- **MA250 估值锚**: 科创50 自 2020-02-03 起, 前 60 个交易日无均线信号(d=0, 不再投); "
             "之后按可用窗口(最多 250 日)计算 MA, 与沪深300 V2 同款。均线为滞后指标, 熊市初期(价格仍高于均线)会延迟触发再投, "
             "牛市初期(价格仍低于均线)会误判为低估--这是用均线择时的固有代价。")
    L.append("- **结构性错配(重要)**: 科创50 的低估日(d≤-8%)**全部集中在 2021-2024**(共 508 个, 2022 年 218 个), "
             "2025-2026 大牛市无低估日。而 V3 的止盈回款大头发生在 2025(43.99 万)与 2026(6.31 万)。"
             "故 V4 的子弹池主要用 2020-2021 的小额回款在 2021-2024 抄底; 2025-2026 的大额回款因已无低估信号, "
             "多数在期末仍以现金形式留存(子弹池余额见第四节)。V4 相对 V3 的增益主要来自 2021-2024 那段低位再投的升值, "
             "而非 2025-2026 回款--这是科创50 行情结构决定的, 与沪深300(2015/2021 两次大波段能完整回补)不尽相同。")
    L.append("- **子弹池再投的极端情况**: 若止盈后长期不出现低估信号(d 始终 > -8%), 子弹池现金长期闲置, 拉低资金利用率"
             "(本回测期末子弹池即有较多闲置); 反之低估信号频繁时(如 2022)子弹池可能被快速抽空, 后续更深底部无钱可投。")
    L.append("- **过拟合风险**: 子弹池阈值(-8%)、加速倍数(3x/5x)、排液比例(2%)等参数, 参照沪深300 V2 设定, "
             "存在对历史走势的拟合依赖; 未来若指数进入长期单边市, 表现可能不及回测。参数不保证未来有效。")
    L.append("- **优化3/6/8 继承自 V3**: DCA 全档、跌破重装、分档卖出的行为与副作用与 V3 完全一致(详见 V3 报告); "
             "V4 仅在止盈回款去向与低位再投上与 V3 不同, `reinvest=False` 时数值与 V3 完全一致(回归校验)。")
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

    # V4(子弹池复利, opt3/6/8 全开) + 回归基线
    events, summary, by_year_pool = run_backtest_v4(prices, reinvest=True)
    # V3(opt3/6/8 全开, 回款闲置) -- 对比 + 回归基线
    _v3_events, v3_summary = run_backtest_v3(prices)
    # V2 / V1 / 纯定投
    _v2_events, v2_summary = run_backtest_v2(prices)
    _v1_events, v1_summary = run_v1_backtest(prices, rearm_mode='on_clear')
    baseline = _pure_dca_baseline(prices)

    # 消融: V3 基线(reinvest=False) vs V4(reinvest=True)
    _, abl_v3 = run_backtest_v4(prices, reinvest=False)[:2]
    abl = {'v3': abl_v3, 'v4': summary}

    # 回归断言: V4 reinvest=False == V3
    assert abl_v3['n_events'] == v3_summary['n_events'], "回归失败: reinvest=False 止盈次数与 V3 不一致"
    assert abs(abl_v3['total_return'] - v3_summary['total_return']) < 1e-9, "回归失败: 总收益率与 V3 不一致"
    assert abs(abl_v3['xirr'] - v3_summary['xirr']) < 1e-9, "回归失败: XIRR 与 V3 不一致"
    assert abs(abl_v3['bullet_pool'] - v3_summary['cash']) < 1e-9, "回归失败: 子弹池与 V3 现金不一致"

    report = build_report(events, summary, by_year_pool, v3_summary, v2_summary, v1_summary, baseline, abl)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    s = summary
    print(f"V4 回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 交易日)")
    print(f"净外部本金(累计定投): {money(s['total_invested'])} 元 | 子弹池再投(内部): {money(s['cum_reinvested'])} 元")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(正常 {s['trigger_counts'].get('normal',0)} / DCA 再触发 {s['trigger_counts'].get('dca_retrigger',0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮盈: {money(s['unrealized'])} 元 | 子弹池: {money(s['bullet_pool'])} 元")
    print(f"V4 总收益: {money(s['total_profit'])} | 总收益率: {pct(s['total_return'])} | "
          f"年化: {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"[回归] V4 reinvest=False == V3: {v3_summary['n_events']}次 / {pct(v3_summary['total_return'])} / "
          f"XIRR {pct(v3_summary['xirr'])} ✓")
    print(f"[对比] V3 总收益率: {pct(v3_summary['total_return'])} | XIRR: {pct(v3_summary['xirr'])}")
    print(f"[对比] V2 总收益率: {pct(v2_summary['total_return'])} | V1: {pct(v1_summary['total_return'])} | "
          f"纯定投: {pct(baseline['total_return'])}")
    print(f"[消融] V3基线(闲置) -> {pct(abl_v3['total_return'])} / XIRR {pct(abl_v3['xirr'])} / "
          f"止盈 {abl_v3['n_events']}次")
    print(f"[消融] V4(子弹池)  -> {pct(s['total_return'])} / XIRR {pct(s['xirr'])} / "
          f"止盈 {s['n_events']}次 / 再投 {money(s['cum_reinvested'])}")
    print(f"边际: 总收益率 +{pct(s['total_return'] - abl_v3['total_return'])} | "
          f"XIRR +{pct(s['xirr'] - abl_v3['xirr'])}")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
