#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深300指数 定投策略 V2(收益最大化版) 回测

相对 V1 的三大改进:
  1. 均线偏离加权定投: 以 250 日均线为估值锚, 低估多投、高估停投
  2. 分档止盈保留底仓: 15%/30%/50% 三档, 各卖一部分, 保留约 29% 底仓吃疯牛
  3. 回款子弹池低位再投: 止盈回款进入子弹池, 低估日加速抄底, 实现复利

数据: index_info 表沪深300(000300)收盘价; PE 字段全为 0 不可用, 故用均线择时。
输出: 同目录 沪深300_定投止盈_回测报告_V2_最大化收益.md
"""
import os
import sys
from collections import defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'data-crawler'))
from app.utils.config import DB_CONFIG  # noqa: E402

import pymysql  # noqa: E402

INDEX_CODE = '000300'
START_DATE = '2010-01-01'
BASE_DAILY = 100.0  # 基础每日定投

# ---- 均线偏离定投档位: d = price/MA250 - 1 ----
# (d 下界, 倍数]  从低到高匹配, 命中即定投 BASE_DAILY*倍数
DCA_BANDS = [
    (-0.999, 4.0),   # d <= -20%: 4x
    (-0.20, 2.5),    # -20% < d <= -10%: 2.5x
    (-0.10, 1.5),    # -10% < d <= 0%: 1.5x
    (0.0, 0.75),     # 0% < d <= +10%: 0.75x
    (0.10, 0.25),    # +10% < d <= +20%: 0.25x
    (0.20, 0.0),     # d > +20%: 停投
]
MA_WINDOW = 250          # 250 日均线
MA_WARMUP = 60           # 不足 60 日时用 1.5x 默认档(视为 d≈0 偏下)
# ---- 止盈档位(持仓收益率, 卖出比例, 名称) ----
TIERS = [
    (0.15, 0.30, '15%'),
    (0.30, 0.40, '30%'),
    (0.50, 0.30, '50%'),
]
REARM_THRESHOLD = 0.08   # 持仓收益率跌破 8% 重新装填三档
# ---- 子弹池低位加速再投 ----
# 低估日(d <= -8%)除定投外, 额外从子弹池买入 = min(pool, 当日定投额 * 加速倍数)
REINVEST_D_THRESHOLD = -0.08
REINVEST_MULT = 3.0      # -8% ~ -20% 加速 3 倍
REINVEST_MULT_DEEP = 5.0  # d <= -20% 加速 5 倍
TRADING_DAYS_PER_YEAR = 244

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '沪深300_定投止盈_回测报告_V2_最大化收益.md'
)


def fetch_prices():
    conn = pymysql.connect(
        host=DB_CONFIG['host'], port=DB_CONFIG['port'],
        user=DB_CONFIG['user'], password=DB_CONFIG['password'],
        database=DB_CONFIG['database'], charset=DB_CONFIG['charset'],
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date, close_price FROM index_info "
                "WHERE index_code=%s AND del_flag='1' AND trade_date>=%s "
                "ORDER BY trade_date",
                (INDEX_CODE, START_DATE),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [(r[0], float(r[1])) for r in rows]


def _xirr(cashflows):
    """XIRR(按实际日期). cashflows: [(date, amount)], 流出负/流入正。二分法求 NPV=0。"""
    if not cashflows:
        return 0.0
    d0 = cashflows[0][0]

    def npv(r):
        return sum(amt / (1.0 + r) ** ((d - d0).days / 365.0) for d, amt in cashflows)

    lo, hi, mid = -0.95, 10.0, 0.0
    for _ in range(300):
        mid = (lo + hi) / 2.0
        v = npv(mid)
        if abs(v) < 1e-2:
            break
        if v > 0:
            lo = mid
        else:
            hi = mid
    return mid


def dca_multiplier(d):
    """根据均线偏离度 d 返回定投倍数。"""
    for lower, mult in DCA_BANDS:
        if d <= lower + 1e-9:
            continue
        # bands 按下界升序; 命中第一个 d <= 上界
    # 直接按区间判定
    if d <= -0.20:
        return 4.0
    if d <= -0.10:
        return 2.5
    if d <= 0.0:
        return 1.5
    if d <= 0.10:
        return 0.75
    if d <= 0.20:
        return 0.25
    return 0.0


def run_backtest(prices):
    total_shares = 0.0
    total_cost = 0.0          # 持仓成本(卖出按比例结转)
    cum_invested = 0.0        # 累计定投(不含子弹池再投)
    cum_reinvested = 0.0      # 累计子弹池再投金额
    cum_realized = 0.0
    bullet_pool = 0.0         # 子弹池现金余额
    armed = {0.15: True, 0.30: True, 0.50: True}
    events = []
    daily_cf = []             # XIRR 现金流: (date, amount), 定投为负
    peak_profit_rate = 0.0
    history = []              # 收盘价序列(用于均线)

    # 年度子弹池统计
    by_year_pool = defaultdict(lambda: {'inflow': 0.0, 'outflow': 0.0, 'end': 0.0})
    by_year_dca = defaultdict(float)  # 年度定投金额(含倍数, 不含再投)

    for trade_date, price in prices:
        history.append(price)
        year = trade_date.year

        # 1) 均线偏离度
        if len(history) < MA_WARMUP:
            d = 0.0
        else:
            window = history[-MA_WINDOW:]
            ma = sum(window) / len(window)
            d = (price - ma) / ma if ma else 0.0

        mult = dca_multiplier(d)
        dca_amount = BASE_DAILY * mult
        by_year_dca[year] += dca_amount

        # 2) 定投买入
        if dca_amount > 0:
            sh = dca_amount / price
            total_shares += sh
            total_cost += dca_amount
            cum_invested += dca_amount
            daily_cf.append((trade_date, -dca_amount))

        # 3) 子弹池低位加速再投(池子比例 + 定投加速双驱动, 加快大额回款消化)
        if d <= REINVEST_D_THRESHOLD and bullet_pool > 0:
            mult_r = REINVEST_MULT_DEEP if d <= -0.20 else REINVEST_MULT
            target = bullet_pool * 0.02 + dca_amount * mult_r
            extra = min(bullet_pool, target)
            if extra > 0:
                sh = extra / price
                total_shares += sh
                total_cost += extra
                cum_reinvested += extra
                bullet_pool -= extra
                by_year_pool[year]['outflow'] += extra

        # 4) 持仓收益率
        if total_cost > 0:
            profit_rate = (total_shares * price - total_cost) / total_cost
        else:
            profit_rate = 0.0
        if profit_rate > peak_profit_rate:
            peak_profit_rate = profit_rate

        # 5) 跌破重置
        if profit_rate < REARM_THRESHOLD:
            armed = {0.15: True, 0.30: True, 0.50: True}

        # 6) 分档止盈(保留底仓)
        for threshold, frac, name in TIERS:
            if profit_rate >= threshold and armed[threshold]:
                shares_before = total_shares
                shares_sold = total_shares * frac
                shares_after = total_shares - shares_sold
                value_before = shares_before * price
                sell_proceeds = shares_sold * price
                cost_before = total_cost
                cost_sold = total_cost * frac
                cost_after = total_cost - cost_sold
                realized = sell_proceeds - cost_sold

                total_shares = shares_after
                total_cost = cost_after
                cum_realized += realized
                bullet_pool += sell_proceeds          # 回款入子弹池
                by_year_pool[year]['inflow'] += sell_proceeds
                armed[threshold] = False

                events.append({
                    'date': trade_date, 'tier': name,
                    'profit_rate': profit_rate, 'price': price,
                    'avg_cost': cost_before / shares_before if shares_before else 0.0,
                    'd': d, 'shares_before': shares_before,
                    'shares_sold': shares_sold, 'shares_after': shares_after,
                    'value_before': value_before, 'sell_proceeds': sell_proceeds,
                    'realized': realized, 'cum_realized': cum_realized,
                    'pool_after': bullet_pool,
                })

        by_year_pool[year]['end'] = bullet_pool

    # 期末
    final_price = prices[-1][1]
    final_value = total_shares * final_price
    unrealized = final_value - total_cost
    total_sell_proceeds = sum(e['sell_proceeds'] for e in events)
    # 净外部本金 = 仅累计定投; 子弹池再投是内部资金循环(来自止盈回款), 不计入本金
    total_in = cum_invested
    # 总收益 = 期末总资产(持仓市值 + 子弹池现金) - 净外部本金
    total_profit = final_value + bullet_pool - cum_invested
    total_return = total_profit / cum_invested if cum_invested else 0.0
    n_days = len(prices)
    years = n_days / TRADING_DAYS_PER_YEAR
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0
    # XIRR: 外部现金流(每日定投流出 + 期末总资产流入), 反映外部资金真实年化回报
    daily_cf.append((prices[-1][0], final_value + bullet_pool))
    xirr_val = _xirr(daily_cf)
    tier_counts = defaultdict(int)
    for e in events:
        tier_counts[e['tier']] += 1

    summary = {
        'first_date': prices[0][0], 'last_date': prices[-1][0],
        'n_days': n_days, 'years': years,
        'min_price': min(p for _, p in prices),
        'max_price': max(p for _, p in prices),
        'cum_invested': cum_invested, 'cum_reinvested': cum_reinvested,
        'total_in': total_in, 'n_events': len(events),
        'tier_counts': dict(tier_counts),
        'cum_realized': cum_realized, 'total_sell_proceeds': total_sell_proceeds,
        'final_shares': total_shares, 'final_cost': total_cost,
        'final_price': final_price, 'final_value': final_value,
        'unrealized': unrealized, 'bullet_pool': bullet_pool,
        'total_profit': total_profit, 'total_return': total_return,
        'annualized': annualized, 'peak_profit_rate': peak_profit_rate,
        'xirr': xirr_val,
    }
    return events, summary, dict(by_year_pool), dict(by_year_dca)


def run_v1_backtest(prices):
    """V1 策略(固定100定投 + 10/15/20%阶梯止盈卖30/60/90% + 跌破10%重置 + 回款闲置)。
    实跑一遍用于精确对比, 避免对比表手填数字。"""
    total_shares = total_cost = cum_invested = cum_realized = cash = 0.0
    armed = {0.10: True, 0.15: True, 0.20: True}
    n_events = 0
    daily_cf = []
    TIERS_V1 = [(0.10, 0.30), (0.15, 0.60), (0.20, 0.90)]
    for trade_date, price in prices:
        sh = 100.0 / price
        total_shares += sh
        total_cost += 100.0
        cum_invested += 100.0
        daily_cf.append((trade_date, -100.0))
        profit_rate = (total_shares * price - total_cost) / total_cost
        if profit_rate < 0.10:
            armed = {0.10: True, 0.15: True, 0.20: True}
        for threshold, frac in TIERS_V1:
            if profit_rate >= threshold and armed[threshold]:
                shares_sold = total_shares * frac
                proceeds = shares_sold * price
                cost_sold = total_cost * frac
                total_shares -= shares_sold
                total_cost -= cost_sold
                cum_realized += proceeds - cost_sold
                cash += proceeds
                armed[threshold] = False
                n_events += 1
                # 注: 回款留在策略现金账户(不提现), 不作为中间现金流, 仅计入期末总资产, 保证与 V2 口径一致
    final_price = prices[-1][1]
    final_value = total_shares * final_price
    daily_cf.append((prices[-1][0], final_value + cash))
    total_profit = final_value + cash - cum_invested
    total_return = total_profit / cum_invested if cum_invested else 0.0
    years = len(prices) / TRADING_DAYS_PER_YEAR
    annualized = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else 0.0
    return {
        'invested': cum_invested, 'n_events': n_events,
        'realized': cum_realized, 'final_value': final_value, 'cash': cash,
        'profit': total_profit, 'return': total_return,
        'annualized': annualized, 'xirr': _xirr(daily_cf),
    }


def money(x): return f"{x:,.2f}"
def shares(x): return f"{x:,.4f}"
def pct(x): return f"{x * 100:.2f}%"


def build_report(events, summary, by_year_pool, by_year_dca, v1):
    s = summary
    L = []
    L.append("# 沪深300 定投策略 V2(收益最大化版) 回测报告")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 沪深300(000300)日线收盘价。")
    L.append("> 脚本: `tasks/backtest_hs300_dca_v2.py`。")
    L.append("> 本报告为 V1(`沪深300_定投止盈_回测报告.md`)的优化版, 目标是最大化收益。")
    L.append("")
    L.append("## 一、V2 相对 V1 的三大改进")
    L.append("")
    L.append("| 维度 | V1(固定定投) | V2(最大化版) |")
    L.append("|---|---|---|")
    L.append("| 定投金额 | 每日固定 100 元 | **均线偏离加权**: 收盘价低于 250 日均线越多投越多(最高 4 倍), 高于均线 20% 停投 |")
    L.append("| 止盈清仓 | 10/15/20% 三档, 20% 档卖 90%, 残仓吃尽涨跌 | **15/30/50% 三档分卖, 保留约 29% 底仓**吃疯牛 |")
    L.append("| 回款处理 | 止盈回款全部闲置, 零复利 | **回款入子弹池, 低估日(d≤-8%)加速抄底**, 实现复利再投 |")
    L.append("| 重置阈值 | 跌破 10% 重置 | 跌破 8% 重置(减少小波动频繁触发) |")
    L.append("")
    L.append("### 设计逻辑")
    L.append("")
    L.append("沪深300 在 2010-2025 呈现**长期低位震荡 + 间歇性大牛市**特征(2014底-2015中 +156%、"
             "2019-2021 +96%, 其间多次回撤)。V1 在顶部照样定投抬高成本、止盈回款闲置、清仓错过疯牛, "
             "导致 15 年总收益仅 10.45%。V2 针对性优化:")
    L.append("")
    L.append("- **低多高少**: 2010-2014、2018、2022-2024 的低位区以 2.5-4 倍力度积累筹码, 压低平均成本; "
             "2015/2021 顶部区停投, 不追高。")
    L.append("- **保留底仓**: 大牛市不分批卖光, 留 29% 底仓继续吃上涨, 避免清仓后踏空。")
    L.append("- **子弹池复利**: 2015 高点止盈套现的钱, 在 2015下半年-2018 低位重新买入, 2021 再次止盈——"
             "把 V1 闲置的 30 万回款变成低位筹码, 赚两轮大波段。")
    L.append("")

    L.append("## 二、策略参数")
    L.append("")
    L.append("| 参数 | 取值 |")
    L.append("|---|---|")
    L.append(f"| 标的 / 区间 | 沪深300(000300), {s['first_date']}~{s['last_date']} |")
    L.append(f"| 基础定投 | {money(BASE_DAILY)} 元/交易日 |")
    L.append("| 均线 | 250 日简单均线(MA250), 不足 60 日按 1.5x 默认 |")
    L.append("| 定投倍数 | d≤-20%:4x · -20~-10%:2.5x · -10~0%:1.5x · 0~+10%:0.75x · +10~+20%:0.25x · >+20%:停投 |")
    L.append("| 止盈档位 | ≥15%卖30% · ≥30%卖40% · ≥50%卖30%(保留底仓) |")
    L.append(f"| 重置阈值 | 持仓收益率跌破 {pct(REARM_THRESHOLD)} 三档重装 |")
    L.append("| 子弹池再投 | d≤-8% 启动; -8~-20% 加速3倍, ≤-20% 加速5倍 |")
    L.append("| 费用 | 不计交易费用、分红、税收; 收盘价近似可投资(可买碎额) |")
    L.append("")

    L.append("## 三、V1 vs V2 核心对比")
    L.append("")
    L.append("> 收益口径统一为: **总收益 = 期末总资产(持仓市值+现金) − 净外部本金(累计定投)**。")
    L.append("> V1 子弹池余额为 0(回款全闲置); V2 期末子弹池现金见下表。")
    L.append("")
    L.append("| 指标 | V1 固定定投 | V2 最大化版 | 变化 |")
    L.append("|---|---|---|---|")
    L.append(f"| 净外部本金(累计定投) | {money(v1['invested'])} | {money(s['total_in'])} | "
             f"{money(s['total_in']-v1['invested'])} |")
    L.append(f"| 止盈次数 | {v1['n_events']} | {s['n_events']} | {s['n_events']-v1['n_events']:+d} |")
    L.append(f"| 累计实现盈亏 | {money(v1['realized'])} | {money(s['cum_realized'])} | "
             f"{money(s['cum_realized']-v1['realized'])} |")
    L.append(f"| 期末持仓市值 | {money(v1['final_value'])} | {money(s['final_value'])} | "
             f"{money(s['final_value']-v1['final_value'])} |")
    L.append(f"| 期末现金(子弹池) | {money(v1['cash'])} | {money(s['bullet_pool'])} | "
             f"{money(s['bullet_pool']-v1['cash'])} |")
    L.append(f"| 期末总资产 | {money(v1['final_value']+v1['cash'])} | "
             f"{money(s['final_value']+s['bullet_pool'])} | "
             f"{money(s['final_value']+s['bullet_pool']-v1['final_value']-v1['cash'])} |")
    L.append(f"| 总收益 | {money(v1['profit'])} | {money(s['total_profit'])} | "
             f"{money(s['total_profit']-v1['profit'])} |")
    L.append(f"| 总收益率(简单总额法) | {pct(v1['return'])} | {pct(s['total_return'])} | "
             f"{pct(s['total_return']-v1['return'])} |")
    L.append(f"| 年化收益率(估, 244日/年) | {pct(v1['annualized'])} | {pct(s['annualized'])} | "
             f"{pct(s['annualized']-v1['annualized'])} |")
    L.append(f"| XIRR(外部现金流年化) | {pct(v1['xirr'])} | {pct(s['xirr'])} | "
             f"{pct(s['xirr']-v1['xirr'])} |")
    L.append("")
    L.append("> XIRR 考虑资金时间价值(15 年陆续投入), 比简单总额法更严谨; V1/V2 均为本脚本实跑测算。")
    L.append("")

    L.append("## 四、V2 回测汇总")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 交易日数 | {s['n_days']} |")
    L.append(f"| 累计定投(均线加权) | {money(s['cum_invested'])} 元 |")
    L.append(f"| 子弹池再投金额(内部循环) | {money(s['cum_reinvested'])} 元 |")
    L.append(f"| 净外部本金(仅累计定投) | {money(s['total_in'])} 元 |")
    L.append(f"| 止盈次数 | {s['n_events']} 次 "
             f"(15%档 {s['tier_counts'].get('15%',0)} / 30%档 {s['tier_counts'].get('30%',0)} / "
             f"50%档 {s['tier_counts'].get('50%',0)}) |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} 元 |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} 元 |")
    L.append(f"| 期末持仓份额 | {shares(s['final_shares'])} 份 |")
    L.append(f"| 期末持仓成本 | {money(s['final_cost'])} 元 |")
    L.append(f"| 期末收盘价 | {money(s['final_price'])} |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} 元 |")
    L.append(f"| 期末浮动盈亏 | {money(s['unrealized'])} 元 |")
    L.append(f"| 期末子弹池现金 | {money(s['bullet_pool'])} 元 |")
    L.append(f"| 区间最高持仓收益率 | {pct(s['peak_profit_rate'])} |")
    L.append(f"| 总收益(期末总资产−净本金) | {money(s['total_profit'])} 元 |")
    L.append(f"| 总收益率(简单总额法) | {pct(s['total_return'])} |")
    L.append(f"| 年化收益率(估, 244日/年) | {pct(s['annualized'])} |")
    L.append(f"| XIRR(外部现金流年化) | {pct(s['xirr'])} |")
    L.append("")

    L.append("## 五、止盈事件明细")
    L.append("")
    L.append(f"共 {s['n_events']} 次止盈。各列: 触发日期 / 档位 / 触发收益率 / 收盘价 / "
             "均线偏离度 / 止盈前份额 / 卖出份额 / 止盈后份额 / 止盈前市值 / 卖出金额 / 本次实现盈亏 / "
             "累计实现盈亏 / 止盈后子弹池余额。")
    L.append("")
    L.append("| # | 日期 | 档位 | 触发收益率 | 收盘价 | 均线偏离 | 止盈前份额 | 卖出份额 | 止盈后份额 | "
             "止盈前市值 | 卖出金额 | 本次实现盈亏 | 累计实现盈亏 | 止盈后子弹池 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(events, 1):
        L.append(
            f"| {i} | {e['date']} | {e['tier']} | {pct(e['profit_rate'])} | {money(e['price'])} | "
            f"{pct(e['d'])} | {shares(e['shares_before'])} | {shares(e['shares_sold'])} | "
            f"{shares(e['shares_after'])} | {money(e['value_before'])} | {money(e['sell_proceeds'])} | "
            f"{money(e['realized'])} | {money(e['cum_realized'])} | {money(e['pool_after'])} |"
        )
    L.append("")

    L.append("## 六、子弹池运作(按年)— 复利核心")
    L.append("")
    L.append("子弹池 = 止盈回款累积的现金; 低估日(d≤-8%)从池中取钱加速抄底。"
             "下表展示每年**流入(止盈回款)→ 流出(低位再投)→ 年末余额**。")
    L.append("")
    L.append("| 年份 | 流入(止盈回款) | 流出(低位再投) | 年末子弹池余额 | 年度定投(均线加权) |")
    L.append("|---|---|---|---|---|")
    all_years = sorted(set(list(by_year_pool.keys()) + list(by_year_dca.keys())))
    for y in all_years:
        p = by_year_pool.get(y, {'inflow': 0.0, 'outflow': 0.0, 'end': 0.0})
        dca = by_year_dca.get(y, 0.0)
        L.append(f"| {y} | {money(p['inflow'])} | {money(p['outflow'])} | {money(p['end'])} | {money(dca)} |")
    L.append("")
    L.append("> 观察: 大牛市年份(如 2015/2021)流入暴增(高位止盈套现), 随后熊市年份流出增加"
             "(低位抄底), 体现**涨时兑现、跌时建仓**的复利循环。")
    L.append("")

    L.append("## 七、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率、分红与税收, "
             "结果略乐观于真实指数基金。")
    L.append("- V2 的均线档位、止盈档位、子弹池加速倍数等参数, 是**基于沪深300 2010-2025 历史走势**"
             "**优化拟合**得来, 存在**过拟合风险**: 未来若指数进入长期单边市(如持续牛市或持续熊市), "
             "表现可能不及回测。参数不保证未来有效。")
    L.append("- **均线择时的固有代价**: MA250 为滞后指标, 行情反转初期会误判(如牛市刚启动时价格仍在均线下方, "
             "会持续重仓; 熊市刚开始时价格仍在均线上方, 会延迟停投)。这是用滞后指标择时的必然权衡。")
    L.append("- **子弹池再投的极端情况**: 若止盈后长期不出现低估信号(d 始终 > -8%), 子弹池现金会长期闲置, "
             "拉低资金利用率; 反之低估信号频繁时子弹池可能提前耗尽。")
    L.append("- V2 收益提升主要来自**两次大波段(2015、2021)的高位兑现与低位回补**, 这是结果依赖的; "
             "若未来无类似级别行情, V2 相对 V1 的优势会收窄。")
    L.append("- 本报告不构成投资建议。")
    L.append("")
    return "\n".join(L)


def main():
    prices = fetch_prices()
    if not prices:
        print("未取到沪深300行情数据", file=sys.stderr)
        sys.exit(1)
    events, summary, by_year_pool, by_year_dca = run_backtest(prices)
    v1 = run_v1_backtest(prices)
    report = build_report(events, summary, by_year_pool, by_year_dca, v1)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    s = summary
    print(f"V2 回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 交易日)")
    print(f"累计定投(加权): {money(s['cum_invested'])} | 子弹池再投: {money(s['cum_reinvested'])} | "
          f"净本金: {money(s['total_in'])}")
    print(f"止盈 {s['n_events']} 次 (15%档 {s['tier_counts'].get('15%',0)}/"
          f"30%档 {s['tier_counts'].get('30%',0)}/50%档 {s['tier_counts'].get('50%',0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} | 期末市值: {money(s['final_value'])} | "
          f"子弹池: {money(s['bullet_pool'])}")
    print(f"V2 总收益: {money(s['total_profit'])} | 总收益率: {pct(s['total_return'])} | "
          f"年化: {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"V1 总收益: {money(v1['profit'])} | 总收益率: {pct(v1['return'])} | "
          f"XIRR: {pct(v1['xirr'])}")
    print(f"报告: {REPORT_PATH}")


if __name__ == '__main__':
    main()
