#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深300指数 每日定投 + 阶梯止盈 回测

策略:
  - 标的: 沪深300 (index_code=000300), 以收盘价模拟可投资净值
  - 每个交易日定投 100 元, 自 2010-01-04 起不间断
  - 止盈档位(持仓收益率):
      >=10%  -> 卖出当时持仓的 30%
      >=15%  -> 卖出当时持仓的 60%
      >=20%  -> 卖出当时持仓的 90%
      > 20%  -> 不动
  - 档位重置: 持仓收益率跌破 10% 后, 三档重新装填, 下一轮上涨再次依次触发
  - 卖出按比例结转成本(平均成本法), 卖出不改变平均成本
  - 每日顺序: 先以当日收盘价定投买入, 再据当日收盘价判定止盈
  - 不计交易费用 / 分红再投 / 税收; 指数点位近似可投资(可买碎额)

输出: 同目录下 沪深300_定投止盈_回测报告.md
"""
import os
import sys
from collections import defaultdict

# 复用项目数据库配置(app.utils.config)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'data-crawler'))
from app.utils.config import DB_CONFIG  # noqa: E402

import pymysql  # noqa: E402

INDEX_CODE = '000300'        # 沪深300
START_DATE = '2010-01-01'    # 从 2010 年起
DAILY_INVEST = 100.0         # 每交易日定投金额(元)

# 止盈档位: (收益率阈值, 卖出比例, 档位名称)
TIERS = [
    (0.10, 0.30, '10%'),
    (0.15, 0.60, '15%'),
    (0.20, 0.90, '20%'),
]
REARM_THRESHOLD = 0.10       # 持仓收益率跌破该值, 三档重新装填
TRADING_DAYS_PER_YEAR = 244  # A股约每年244个交易日, 用于年化估算

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '沪深300_定投止盈_回测报告.md'
)


def fetch_prices():
    """从 index_info 取沪深300收盘价, 按交易日升序。"""
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


def run_backtest(prices):
    """执行回测, 返回 (events, summary)。"""
    total_shares = 0.0       # 当前持仓份额
    total_cost = 0.0         # 当前持仓对应的投入成本(卖出按比例结转)
    total_invested = 0.0     # 累计定投金额
    cum_realized = 0.0       # 累计实现盈亏
    armed = {0.10: True, 0.15: True, 0.20: True}  # 三档是否装填

    events = []
    peak_profit_rate = 0.0   # 历史最高持仓收益率(观察用)

    for trade_date, price in prices:
        # 1) 每日定投买入(当日收盘价)
        buy_shares = DAILY_INVEST / price
        total_shares += buy_shares
        total_cost += DAILY_INVEST
        total_invested += DAILY_INVEST

        # 2) 持仓收益率 = (市值 - 成本) / 成本 = (现价 - 平均成本) / 平均成本
        profit_rate = (total_shares * price - total_cost) / total_cost
        if profit_rate > peak_profit_rate:
            peak_profit_rate = profit_rate

        # 3) 跌破10% -> 三档重新装填
        if profit_rate < REARM_THRESHOLD:
            armed = {0.10: True, 0.15: True, 0.20: True}

        # 4) 依次判定 10% -> 15% -> 20%
        for threshold, frac, name in TIERS:
            if profit_rate >= threshold and armed[threshold]:
                shares_before = total_shares
                shares_sold = total_shares * frac
                shares_after = total_shares - shares_sold

                value_before = shares_before * price
                sell_proceeds = shares_sold * price
                value_after = shares_after * price

                cost_before = total_cost
                cost_sold = total_cost * frac      # 平均成本法: 按比例结转
                cost_after = total_cost - cost_sold
                realized = sell_proceeds - cost_sold

                total_shares = shares_after
                total_cost = cost_after
                cum_realized += realized
                armed[threshold] = False

                events.append({
                    'date': trade_date,
                    'tier': name,
                    'profit_rate': profit_rate,
                    'price': price,
                    'avg_cost': cost_before / shares_before if shares_before else 0.0,
                    'shares_before': shares_before,
                    'shares_sold': shares_sold,
                    'shares_after': shares_after,
                    'value_before': value_before,
                    'sell_proceeds': sell_proceeds,
                    'value_after': value_after,
                    'realized': realized,
                    'cum_realized': cum_realized,
                })
                # 比例卖出不改变平均成本, profit_rate 不变, 无需重算

    # 期末状态
    final_price = prices[-1][1]
    final_value = total_shares * final_price
    unrealized = final_value - total_cost
    total_sell_proceeds = sum(e['sell_proceeds'] for e in events)
    total_profit = final_value + total_sell_proceeds - total_invested
    total_return = total_profit / total_invested if total_invested else 0.0

    n_days = len(prices)
    years = n_days / TRADING_DAYS_PER_YEAR
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0

    tier_counts = defaultdict(int)
    for e in events:
        tier_counts[e['tier']] += 1

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
        'cum_realized': cum_realized,
        'total_sell_proceeds': total_sell_proceeds,
        'final_shares': total_shares,
        'final_cost': total_cost,
        'final_price': final_price,
        'final_value': final_value,
        'unrealized': unrealized,
        'total_profit': total_profit,
        'total_return': total_return,
        'annualized': annualized,
        'peak_profit_rate': peak_profit_rate,
    }
    return events, summary


# ---------- 格式化辅助 ----------
def money(x):
    return f"{x:,.2f}"


def shares(x):
    return f"{x:,.4f}"


def pct(x):
    return f"{x * 100:.2f}%"


def build_report(events, summary):
    lines = []
    lines.append("# 沪深300 每日定投 + 阶梯止盈 回测报告")
    lines.append("")
    lines.append("> 数据来源: `personal-finance.index_info` 表, 沪深300指数(index_code=000300)日线收盘价。")
    lines.append("> 回测脚本: `tasks/backtest_hs300_dca.py`。")
    lines.append("")
    lines.append("## 一、策略与假设")
    lines.append("")
    lines.append("| 项 | 设定 |")
    lines.append("|---|---|")
    lines.append("| 标的 | 沪深300指数(000300), 以收盘价模拟可投资净值 |")
    lines.append(f"| 定投 | 每个交易日投入 {money(DAILY_INVEST)} 元, 自 {summary['first_date']} 起不间断 |")
    lines.append("| 止盈档位 | 持仓收益率 ≥10% 卖出当时持仓 30%; ≥15% 卖 60%; ≥20% 卖 90%; >20% 不动 |")
    lines.append("| 档位重置 | 持仓收益率跌破 10% 后, 三档重新装填, 下一轮上涨再次依次触发 |")
    lines.append("| 持仓收益率 | (持仓市值 − 持仓成本) / 持仓成本, 等价于 (现价 − 平均成本) / 平均成本 |")
    lines.append("| 成本结转 | 卖出按比例结转成本(平均成本法), 卖出不改变平均成本 |")
    lines.append("| 每日顺序 | 先以当日收盘价定投买入, 再据当日收盘价判定止盈 |")
    lines.append("| 费用 | 不计交易费用、分红再投、税收; 指数点位近似可投资(可买碎额) |")
    lines.append("")

    lines.append("## 二、数据概览")
    lines.append("")
    lines.append("| 项 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| 交易日数 | {summary['n_days']} |")
    lines.append(f"| 回测区间 | {summary['first_date']} ~ {summary['last_date']} |")
    lines.append(f"| 收盘价区间 | {money(summary['min_price'])} ~ {money(summary['max_price'])} |")
    lines.append(f"| 区间内最高持仓收益率 | {pct(summary['peak_profit_rate'])} |")
    lines.append("")

    lines.append("## 三、回测汇总")
    lines.append("")
    s = summary
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| 累计定投金额 | {money(s['total_invested'])} 元 |")
    lines.append(f"| 定投天数 | {s['n_days']} 个交易日 |")
    lines.append(f"| 止盈次数(合计) | {s['n_events']} 次 |")
    lines.append(f"| └ 10%档 | {s['tier_counts'].get('10%', 0)} 次 |")
    lines.append(f"| └ 15%档 | {s['tier_counts'].get('15%', 0)} 次 |")
    lines.append(f"| └ 20%档 | {s['tier_counts'].get('20%', 0)} 次 |")
    lines.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} 元 |")
    lines.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} 元 |")
    lines.append(f"| 期末持仓份额 | {shares(s['final_shares'])} 份 |")
    lines.append(f"| 期末持仓成本 | {money(s['final_cost'])} 元 |")
    lines.append(f"| 期末收盘价 | {money(s['final_price'])} |")
    lines.append(f"| 期末持仓市值 | {money(s['final_value'])} 元 |")
    lines.append(f"| 期末浮动盈亏 | {money(s['unrealized'])} 元 |")
    lines.append(f"| 总收益(实现+浮盈) | {money(s['total_profit'])} 元 |")
    lines.append(f"| 总收益率 | {pct(s['total_return'])} |")
    lines.append(f"| 年化收益率(估, 244日/年) | {pct(s['annualized'])} |")
    lines.append("")

    lines.append("## 四、止盈事件明细")
    lines.append("")
    lines.append(f"共 {s['n_events']} 次止盈。下表逐次记录: 触发日期 / 触发档位 / 触发时持仓收益率 / "
                 "收盘价 / 止盈前份额 / 卖出份额 / 止盈后份额 / 止盈前市值 / 卖出金额 / 止盈后市值 / "
                 "本次实现盈亏 / 累计实现盈亏。")
    lines.append("")
    lines.append("| # | 日期 | 档位 | 触发收益率 | 收盘价 | 止盈前份额 | 卖出份额 | 止盈后份额 | "
                 "止盈前市值 | 卖出金额 | 止盈后市值 | 本次实现盈亏 | 累计实现盈亏 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(events, 1):
        lines.append(
            f"| {i} | {e['date']} | {e['tier']} | {pct(e['profit_rate'])} | {money(e['price'])} | "
            f"{shares(e['shares_before'])} | {shares(e['shares_sold'])} | {shares(e['shares_after'])} | "
            f"{money(e['value_before'])} | {money(e['sell_proceeds'])} | {money(e['value_after'])} | "
            f"{money(e['realized'])} | {money(e['cum_realized'])} |"
        )
    lines.append("")

    # 按年分布
    lines.append("## 五、止盈事件按年分布")
    lines.append("")
    by_year = defaultdict(lambda: {'count': 0, 'proceeds': 0.0, 'realized': 0.0})
    for e in events:
        y = e['date'].year
        by_year[y]['count'] += 1
        by_year[y]['proceeds'] += e['sell_proceeds']
        by_year[y]['realized'] += e['realized']
    lines.append("| 年份 | 止盈次数 | 卖出回款(元) | 实现盈亏(元) |")
    lines.append("|---|---|---|---|")
    for y in sorted(by_year):
        d = by_year[y]
        lines.append(f"| {y} | {d['count']} | {money(d['proceeds'])} | {money(d['realized'])} |")
    lines.append("")

    lines.append("## 六、说明")
    lines.append("")
    lines.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, "
                 "结果略乐观于真实指数基金定投。")
    lines.append("- 持仓收益率为**组合层面**的(市值−成本)/成本; 每日新增定投会抬高平均成本, "
                 "因此即便行情横盘, 持仓收益率也会被持续稀释。")
    lines.append("- 止盈档位在持仓收益率**自下而上依次穿越**时触发; 跌破 10% 后重新装填, "
                 "故 10% 档会在多轮小级别上涨中反复触发, 15%/20% 档仅在强势行情中出现。")
    lines.append("- 卖出按比例结转成本(平均成本法), 单次止盈不改变剩余持仓的平均成本。")
    lines.append("- 年化收益率为按 244 交易日/年的粗略估算, 仅供参考。")
    lines.append("")
    return "\n".join(lines)


def main():
    prices = fetch_prices()
    if not prices:
        print("未取到沪深300行情数据", file=sys.stderr)
        sys.exit(1)
    events, summary = run_backtest(prices)
    report = build_report(events, summary)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    # 控制台简要输出
    s = summary
    print(f"回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 个交易日)")
    print(f"累计定投: {money(s['total_invested'])} 元")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(10%档 {s['tier_counts'].get('10%', 0)}, "
          f"15%档 {s['tier_counts'].get('15%', 0)}, "
          f"20%档 {s['tier_counts'].get('20%', 0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计卖出回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮动盈亏: {money(s['unrealized'])} 元")
    print(f"总收益: {money(s['total_profit'])} 元 | 总收益率: {pct(s['total_return'])} | "
          f"年化(估): {pct(s['annualized'])}")
    print(f"报告已生成: {REPORT_PATH}")


if __name__ == '__main__':
    main()
