#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯递增止盈(50%清仓封顶 + 全档 DCA 再触发) 回测 V3

相对 V2(`backtest_kc50_dca_v2.py`)的策略变更:
  1. 正常止盈 9 档(10%/15%/20%/25%/30%/35%/40%/45%/50%), 卖出比例 = 2×档位:
     10%卖20%、15%卖30%、20%卖40%…45%卖90%、50%卖100%(清仓)。越涨卖越多, 高位重锁利。
  2. 重装阈值改为 L−2.5%(V2 为 L−5%): 档位 L 触发后, 持仓收益率跌破 L−2.5% 才重装
     (10%跌破7.5%、15%跌破12.5%…)。比 V2 更迟重装, 避免噪声翻转。
  3. DCA 再触发推广到所有非封顶档位(10%~45%): 触发档位 L 后, 若收益率持续在 [L, L+5%) 震荡,
     当「自该档上次减仓累计定投 ≥ 该档上次卖出额一半」时, 再卖一次该档(卖比仍 = 2L)。
     各档位独立追踪自己的累计定投与上次卖出额, 互不干扰(V2 仅 15% 档适用、且为全局追踪)。
  4. 50% 档封顶清仓: 卖 100% 清空持仓(当日定投份额一并卖出), 之后靠每日定投重新积累。
     故 V3 不再是「永不空仓」--50% 清仓后持仓归零, 待收益率跌回近 0 触发全档重装。

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
from tasks.backtest_kc50_dca_v2 import run_backtest_v2  # noqa: E402  (V3 vs V2 同区间对比)

FIRST_TIER = 0.10         # 首个止盈档(10%)
TIER_STEP = 0.05          # 档位间距(每涨 5%)
LAST_TIER = 0.50          # 封顶档(50% 清仓)
REARM_OFFSET = 0.025      # 重装阈值: 跌破 L−2.5% 重装(V2 为 L−5%)

# 9 个止盈档: 10%/15%/20%/25%/30%/35%/40%/45%/50%
TIERS = [round(FIRST_TIER + TIER_STEP * i, 10)
         for i in range(int(round((LAST_TIER - FIRST_TIER) / TIER_STEP)) + 1)]

# 各档卖出比例 = 2×档位(10%->20%, 15%->30%, …, 50%->100%)
TIER_SELL_FRAC = {L: round(2.0 * L, 10) for L in TIERS}

# DCA 再触发适用档: 排除 50% 封顶档(其 [50%,55%) 区间不存在, 且清仓后无 DCA 意义)
DCA_TIERS = [L for L in TIERS if L < LAST_TIER]

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告_V3.md'
)


def _tier_label(L):
    return f"{int(round(L * 100))}%"


class V3Engine:
    """阶梯递增止盈状态机: 按档位独立追踪 armed / DCA 累计 / 上次卖出额。

    暴露内部状态(self.armed / self.dca_since_last_sell / self.last_sell_proceeds)
    便于单元测试白盒验证「按档位独立」不变量。

    参数化配置: tiers / tier_sell_frac / rearm_offset / tier_step / daily_invest,
    默认为 V3 配置(10% 起, 9 档到 50%)。V4 等变体可传入不同档位集复用同一引擎
    (如 V4 去掉 10% 档, 15% 起 8 档)。
    """

    def __init__(self, tiers=None, tier_sell_frac=None, rearm_offset=None,
                 tier_step=None, daily_invest=None):
        self.tiers = list(tiers) if tiers is not None else list(TIERS)
        self.tier_sell_frac = (dict(tier_sell_frac) if tier_sell_frac is not None
                               else dict(TIER_SELL_FRAC))
        self.rearm_offset = rearm_offset if rearm_offset is not None else REARM_OFFSET
        self.tier_step = tier_step if tier_step is not None else TIER_STEP
        self.daily_invest = daily_invest if daily_invest is not None else DAILY_INVEST
        # DCA 再触发适用档: 排除卖 100% 的封顶档(清仓档无 DCA 意义)
        self.dca_tiers = [L for L in self.tiers if self.tier_sell_frac[L] < 1.0]
        self.last_tier = self.tiers[-1]

        self.armed = {L: True for L in self.tiers}            # 各档是否装填
        self.total_shares = 0.0                               # 当前持仓份额
        self.total_cost = 0.0                                 # 当前持仓成本(卖出按比例结转)
        self.total_invested = 0.0                             # 累计定投金额
        self.cum_realized = 0.0                               # 累计实现盈亏
        # 按档位独立追踪 DCA 再触发状态
        self.dca_since_last_sell = {L: 0.0 for L in self.tiers}  # 各档自上次减仓以来的累计定投
        self.last_sell_proceeds = {L: 0.0 for L in self.tiers}   # 各档上一次卖出额(半额判定基准)
        self.events = []
        self.peak_profit_rate = 0.0
        self.daily_cf = []                                    # XIRR 现金流

    def _fire(self, trade_date, L, price, profit_rate, trigger, dca_at_trigger):
        """卖出当前持仓的 TIER_SELL_FRAC[L], 记录事件, 更新状态。"""
        shares_before = self.total_shares
        frac = self.tier_sell_frac[L]
        shares_sold = self.total_shares * frac
        shares_after = self.total_shares - shares_sold

        value_before = shares_before * price
        sell_proceeds = shares_sold * price
        value_after = shares_after * price

        cost_before = self.total_cost
        cost_sold = self.total_cost * frac               # 平均成本法: 按比例结转
        cost_after = self.total_cost - cost_sold
        realized = sell_proceeds - cost_sold

        self.total_shares = shares_after
        self.total_cost = cost_after
        self.cum_realized += realized

        # 该档本次减仓: 重置该档 DCA 累计, 记录本次卖出额(供下次 DCA 半额判定)
        self.dca_since_last_sell[L] = 0.0
        self.last_sell_proceeds[L] = sell_proceeds

        self.events.append({
            'date': trade_date,
            'tier': _tier_label(L),
            'trigger': trigger,                     # 'normal' | 'dca_retrigger'
            'profit_rate': profit_rate,
            'price': price,
            'avg_cost': cost_before / shares_before if shares_before else 0.0,
            'shares_before': shares_before,
            'shares_sold': shares_sold,
            'shares_after': shares_after,
            'value_before': value_before,           # 止盈前持仓金额(市值)
            'cost_before': cost_before,
            'cost_after': cost_after,
            'sell_proceeds': sell_proceeds,         # 止盈金额(卖出回款)
            'value_after': value_after,             # 止盈后持仓金额(市值)
            'realized': realized,
            'cum_realized': self.cum_realized,
            'dca_at_trigger': dca_at_trigger,       # 触发前该档累计加仓金额(可追溯)
        })

    def step(self, trade_date, price):
        """推进一个交易日: 定投买入 -> 判定止盈。返回当日持仓收益率。"""
        # 1) 每日定投买入
        buy_shares = self.daily_invest / price
        self.total_shares += buy_shares
        self.total_cost += self.daily_invest
        self.total_invested += self.daily_invest
        self.daily_cf.append((trade_date, -self.daily_invest))
        # 当日定投计入每个档位的累计(各档独立追踪, 触发时按档重置)
        for L in self.tiers:
            self.dca_since_last_sell[L] += self.daily_invest

        # 2) 持仓收益率
        profit_rate = ((self.total_shares * price - self.total_cost) / self.total_cost
                       if self.total_cost > 0 else 0.0)
        if profit_rate > self.peak_profit_rate:
            self.peak_profit_rate = profit_rate

        # 3) 重装: 档位 L 已触发 且 收益率 < L−rearm_offset -> 重装(清空该档 DCA 状态)
        for L in self.tiers:
            if not self.armed[L] and profit_rate < L - self.rearm_offset:
                self.armed[L] = True
                self.dca_since_last_sell[L] = 0.0
                self.last_sell_proceeds[L] = 0.0

        # 4) 正常止盈(档位升序): 收益率 ≥ L 且已装填 -> 卖 tier_sell_frac[L]
        for L in self.tiers:
            if profit_rate >= L and self.armed[L]:
                dca_snapshot = self.dca_since_last_sell[L]
                self._fire(trade_date, L, price, profit_rate, 'normal', dca_snapshot)
                self.armed[L] = False

        # 5) DCA 再触发(非封顶档, 升序): 档 L 未装填 且 [L, L+step) 且 该档累计定投 ≥ 该档上次卖出额一半
        #    各档 [L, L+step) 区间互斥, 同日最多一档满足; 命中后 break。
        for L in self.dca_tiers:
            if (not self.armed[L]
                    and L <= profit_rate < L + self.tier_step
                    and self.last_sell_proceeds[L] > 0
                    and self.dca_since_last_sell[L] >= self.last_sell_proceeds[L] / 2.0):
                dca_snapshot = self.dca_since_last_sell[L]
                self._fire(trade_date, L, price, profit_rate, 'dca_retrigger', dca_snapshot)
                # DCA 再触发不改 armed 状态(该档保持未装填), 可连续触发
                break

        return profit_rate


def run_backtest_v3(prices):
    """执行 V3 回测, 返回 (events, summary)。状态机见模块文档。"""
    eng = V3Engine()
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


def build_report(events, summary, v2_summary, v1_summary, baseline):
    L = []
    s = summary
    L.append("# 科创50 定投止盈回测 V3(递增卖比 + 50% 清仓封顶 + 全档 DCA 再触发)")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca_v3.py`。")
    L.append("> 本报告为 V2(`科创50_定投止盈_回测报告_V2.md`)的策略升级版。")
    L.append("> 对比口径: V3/V2/V1/纯定投均用**同一数据区间**(本报告数据日)重跑, 公平对比。")
    L.append("")

    L.append("## 一、V3 相对 V2 的策略变更")
    L.append("")
    L.append("| 维度 | V2(永不空仓) | V3(递增卖比+50%清仓) |")
    L.append("|---|---|---|")
    L.append("| 止盈档位 | 15% 起, 每涨 5% 一档, 无封顶 | **10% 起, 每涨 5% 一档, 50% 封顶**(共 9 档) |")
    L.append("| 卖出比例 | 每档固定卖当前 30% | **卖比 = 2×档位**(10%卖20%、15%卖30%…50%卖100%), 越涨卖越多 |")
    L.append("| 持仓状态 | **永不空仓**, 每次留 70% 底仓 | 50% 档**清仓封顶**, 其余档留底仓; 触 50% 后持仓归零重建 |")
    L.append("| 重装阈值 | 跌破 L−5% 重装 | **跌破 L−2.5% 重装**(更迟重装, 抗噪声) |")
    L.append("| DCA 再触发 | 仅 15% 档, **全局**追踪累计定投 | **推广到 10%~45% 全部 8 档**, **按档位独立**追踪 |")
    L.append("| DCA 区间 | 仅 [15%,20%) | [10%,15%)…[45%,50%) 共 8 个震荡区间各档独立 |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("V2 的「每档固定卖 30%、永不空仓」在强趋势市中保留了过多底仓, 高位锁利不足; 且 DCA 再触发"
             "仅限 15% 档, 无法处理更高档位的长期震荡。V3 改为**递增卖比**: 档位越高卖出比例越大"
             "(10%卖20%→50%卖100%), 在确保低档轻仓留底、高档重仓锁利的同时, 50% 封顶清仓兑现全部浮盈。"
             "重装阈值收紧至 L−2.5%, 减少噪声翻转; DCA 再触发推广到全部 8 个非封顶档位并**按档独立追踪**"
             "--每个档位记录自己的「上次减仓以来累计定投」与「上次卖出额」, 互不干扰, "
             "使任意两档间的长期横盘都能定期收割, 提高资金周转。")
    L.append("")

    L.append("## 二、策略与假设")
    L.append("")
    L.append("| 项 | 设定 |")
    L.append("|---|---|")
    L.append("| 标的 | 科创50指数(000688), 以收盘价模拟可投资净值 |")
    L.append(f"| 定投 | 每个交易日投入 {money(DAILY_INVEST)} 元, 自 {s['first_date']} 起不间断(无论涨跌) |")
    L.append("| 止盈档位 | 持仓收益率 ≥10%/15%/20%/25%/30%/35%/40%/45%/50% 共 9 档, 每涨 5% 一档 |")
    L.append("| 卖出比例 | **卖比 = 2×档位**: 10%卖20%、15%卖30%、20%卖40%、25%卖50%、30%卖60%、"
             "35%卖70%、40%卖80%、45%卖90%、**50%卖100%(清仓)** |")
    L.append("| DCA 再触发 | 档 L 触发后, 若 L≤收益率<L+5% 且「该档自上次减仓累计定投 ≥ 该档上次卖出额一半」, "
             "再卖一次该档(卖比仍 = 2L); 适用于 10%~45% 共 8 档, 各档独立追踪 |")
    L.append("| 重装规则 | 档位 L 在收益率跌破 **L−2.5%** 时重装(10%:跌破7.5% · 15%:跌破12.5% · … · 50%:跌破47.5%) |")
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
    # 各档触发次数(列全部 9 档, 含 0 次未触发, 呼应核心发现中 50% 未触发)
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

    # 对比: V3 vs V2 vs V1 vs 纯定投
    L.append("## 七、V3 vs V2 vs V1 vs 纯定投 对比")
    L.append("")
    L.append("> 收益口径统一: **总收益 = 期末总资产(持仓市值+回款现金) − 累计定投**。")
    L.append("> 四者均用同一数据区间重跑, 公平对比。V2=永不空仓(每档卖30%); "
             "V1=10/15/20% 且 20% 清仓; 纯定投=不止盈持有到期末。")
    L.append("")
    v2, v1, b = v2_summary, v1_summary, baseline
    L.append("| 指标 | V3(递增卖比+50%清仓) | V2(永不空仓) | V1(20%清仓) | 纯定投不止盈 |")
    L.append("|---|---|---|---|---|")
    L.append(f"| 止盈次数 | {s['n_events']} | {v2['n_events']} | {v1['n_events']} | 0 |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(v2['total_sell_proceeds'])} | "
             f"{money(v1['total_sell_proceeds'])} | 0 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(v2['cum_realized'])} | "
             f"{money(v1['cum_realized'])} | 0 |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(v2['final_value'])} | "
             f"{money(v1['final_value'])} | {money(b['final_value'])} |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['cash'])} | {money(v2['final_value']+v2['cash'])} | "
             f"{money(v1['final_value']+v1['cash'])} | {money(b['final_value'])} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(v2['total_return'])} | "
             f"{pct(v1['total_return'])} | {pct(b['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(v2['xirr'])} | {pct(v1['xirr'])} | - |")
    L.append("")

    # 核心发现(动态, 基于实际触发数据)
    v3_tr = s['total_return']
    v2_tr = v2['total_return']
    v1_tr = v1['total_return']
    b_tr = b['total_return']
    d_v3_v2 = v3_tr - v2_tr
    fifty_triggered = s['tier_counts'].get('50%', 0) > 0
    peak_v3 = s['peak_profit_rate']
    peak_v2 = v2['peak_profit_rate']
    n10_v3 = s['tier_counts'].get('10%', 0)
    L.append(f"> **核心发现**: V3 总收益率 {pct(v3_tr)}, V2 为 {pct(v2_tr)}, "
             f"V3 − V2 = {pct(d_v3_v2)}({'高于' if d_v3_v2 > 0 else '低于'} V2); "
             f"V1 {pct(v1_tr)}, 纯定投 {pct(b_tr)}。")
    if not fifty_triggered:
        L.append(f"> **50% 清仓未触发**: 本回测区间 V3 最高持仓收益率仅 {pct(peak_v3)}"
                 f"(V2 为 {pct(peak_v2)}), 未达 50% 档, 故 50% 清仓封顶规则在本数据集**未实际生效**, "
                 f"V3 全程未空仓。V3 实际表现为「10% 起步的递增卖比 + 全档 DCA」(无清仓)。"
                 f"50% 清仓逻辑已用合成数据单测验证, 但本行情峰值不足, 未触发。")
    L.append(f"> V3 弱于 V2 的真实根因(本数据集 V3 全程未清仓, 50% 非因素):")
    L.append(f"> ①**10% 档过早、过频削薄底仓**: V3 设有 10% 档(卖 20%), 本回测触发 {n10_v3} 次, "
             f"在仅 10%~15% 的小涨中就卖出 20% 底仓; V2 从 15% 起卖, 底仓更厚。")
    L.append(f"> ②**递增卖比在中高位过度减仓**: 20%/25%/30%/35% 档分别卖 40%/50%/60%/70%, "
             f"单边大涨时持仓迅速降至个位数百分比--如 2025-08-22 一波 15/20/25/30/35% 五档连触后, "
             f"底仓仅剩约 2.5%(0.7×0.6×0.5×0.4×0.3); 而 V2 各档固定卖 30%, 同波段后仍剩 0.7⁴≈24%, "
             f"留底仓约为 V3 的 10 倍, 后续科创50 从 1,365 涨到 2,186(+60%) 时 V2 厚底仓吃到远多于 V3 的市值增长。")
    L.append(f"> ③**锁利总额反更低**: 持仓削薄后单次卖出基数变小, V3 累计实现盈亏 "
             f"{money(s['cum_realized'])} 反而**低于** V2 的 {money(v2['cum_realized'])}, "
             f"回款 {money(s['cash'])} 也低于 V2 的 {money(v2['cash'])}--"
             f"递增卖比在「峰值未超 40%」的行情里, 锁利与留仓两头不讨好。")
    L.append(f"> **结论**: 在科创50这种「长期上行、峰值未超 50%」的行情里, V2 的「轻仓止盈(每档30%)+永不空仓」"
             f"优于 V3 的「递增卖比+10%起步」。V3 递增卖比的设计本意是「高位重锁利」, 需行情涨到 40%~50% "
             f"才能体现优势, 本数据集未覆盖(最高仅 35.42%)。V3 的真正潜力场景是**大牛市/高波动见顶**行情; "
             f"当前数据下, V3 的全档 DCA 再触发(6 次)与更细的 10% 档反而过度交易、抬高机会成本。"
             f"无论 V3/V2, 止盈总收益仍远低于纯定投({pct(b_tr)}), 根因依旧是**回款闲置零复利**"
             f"--最大优化点仍是「回款再投」, 把高位套现的钱在低位重新买入。")
    L.append("")

    L.append("## 八、可优化方向")
    L.append("")
    L.append("针对科创50 **高波动、强趋势、成长风格** 特性, 在 V3 基础上可考虑:")
    L.append("")
    L.append("1. **回款再投(子弹池复利)**: 当前止盈回款闲置, 零复利。可让回款进入子弹池, 在低位"
             "(收盘价低于 250 日均线 8% 以上)加速抄底, 把高位套现的钱变成低位筹码。"
             "沪深300 V2 已验证此优化可显著提升总收益, 是当前所有止盈版本的最大杠杆。")
    L.append("2. **50% 清仓后回款再投**: V3 的 50% 清仓兑现全部浮盈, 但回款闲置。若清仓回款在"
             "随后下跌中分批再投, 可形成「50% 清仓 → 低位回补」的完整大波段高抛低吸, "
             "显著优于清仓后单纯重新定投。需回测验证再投时点。")
    L.append("3. **重装阈值动态化**: 当前「跌破 L−2.5% 重装」为固定百分点。可改为跌破 250 日均线或"
             "移动平均成本重装, 更贴合趋势反转; 或给重装加冷却期避免频繁翻转。L−2.5% 比 V2 的 L−5% "
             "更迟重装, 已减少噪声, 但仍可在档位间差异化(低档更敏感、高档更迟钝)。")
    L.append("4. **DCA 再触发半额阈值调整**: 当前「累计定投 ≥ 上次卖出额一半」即再触发。可调高到 "
             "60%~80% 减少震荡市过度减仓, 或按档位差异化(低档半额、高档更高比例), 平衡资金周转与底仓保留。")
    L.append("5. **止盈档位动态化**: 当前 10%~50% 固定档。可结合 PE 历史分位、波动率动态调整--"
             "高估区提前止盈、低估区放宽阈值。⚠️ index_info 中科创50的 pe_ratio/pe_percentile "
             "当前为 0(未采集), 落地需先补数据。")
    L.append("6. **卖出比例曲线优化**: 当前卖比 = 2×档位(线性)。可改为凸性曲线(低档更轻、高档更重), "
             "或结合波动率--高波动指数(科创50)低档就应多卖以锁定, 低波动则相反。需回测对比。")
    L.append("7. **均线/估值加权定投**: 当前无论涨跌每日固定 300 元, 顶部照样定投抬高成本。"
             "可按收盘价相对 250 日均线偏离度加权--低估多投、高估停投, 压低平均成本。"
             "科创50波动大于沪深300, 潜力更大。")
    L.append("8. **止盈基准优化**: 当前止盈看「组合整体收益率」, 每日新增定投会持续稀释收益率, "
             "导致横盘时收益率被压低、止盈推迟。可改为按「最早批次成本」或「移动平均成本」分批止盈, "
             "反映不同批次真实盈亏。")
    L.append("")

    L.append("## 九、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, 结果略乐观于真实科创50指数基金定投。")
    L.append("- **50% 清仓**: 50% 档卖出 100%, 持仓归零(含当日定投份额)。清仓后靠每日定投重新积累, "
             "收益率跌回近 0 时全档重装。故 V3 不再是「永不空仓」--触 50% 后存在空仓期。")
    L.append("- **递增卖比**: 同日从低档到高档依次触发时, 每档卖当前持仓的 2L 比例, 累计留存 = "
             "∏(1−2Lᵢ)。如单日涨到 50%, 9 档依次触发后留存 ≈ 0(50% 档清仓); 涨到 45% 则留存 "
             "0.8×0.7×0.6×0.5×0.4×0.3×0.2×0.1 ≈ 0.004%, 仍留极少底仓。")
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

    events, summary = run_backtest_v3(prices)
    _v2_events, v2_summary = run_backtest_v2(prices)        # 同区间重跑 V2, 公平对比
    _v1_events, v1_summary = run_v1_backtest(prices, rearm_mode='on_clear')
    baseline = _pure_dca_baseline(prices)

    report = build_report(events, summary, v2_summary, v1_summary, baseline)
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
    print(f"[对比] V2 总收益率: {pct(v2_summary['total_return'])} | XIRR: {pct(v2_summary['xirr'])} | "
          f"止盈 {v2_summary['n_events']} 次")
    print(f"[对比] V1 总收益率: {pct(v1_summary['total_return'])} | XIRR: {pct(v1_summary['xirr'])} | "
          f"止盈 {v1_summary['n_events']} 次")
    print(f"[对比] 纯定投不止盈 总收益率: {pct(baseline['total_return'])}")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
