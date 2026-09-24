#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""科创50指数 每日定投 + 阶梯止盈 回测

策略(用户指定):
  - 标的: 科创50 (index_code=000688), 以收盘价模拟可投资净值
  - 每个交易日定投 300 元, 自首个交易日(2020-02-03)起不间断(无论涨跌)
  - 止盈档位(持仓收益率):
      >=10%  -> 卖出当时持仓的 30%
      >=15%  -> 卖出当时持仓的 30%
      >=20%  -> 一次性卖出全部(100%)
  - 档位重装(用户选择"仅20%清仓后重装"): 只有 20% 档清仓后, 三档才重新装填;
    10%/15% 触发后在本轮周期内不再触发, 直到出现一次 20% 清仓。
    (为做敏感性对比, 引擎支持 rearm_mode='on_dip': 跌破 10% 即重装, 即沪深300 V1 口径)
  - 卖出按比例结转成本(平均成本法), 卖出不改变平均成本
  - 每日顺序: 先以当日收盘价定投买入, 再据当日收盘价判定止盈
  - 回款处理: 止盈回款留作现金, 不自动再投(简单策略; 再投列为优化方向)
  - 不计交易费用 / 分红再投 / 税收; 指数点位近似可投资(可买碎额)

输出: 同目录下 科创50_定投止盈_回测报告.md
"""
import os
import sys
from collections import defaultdict

# 复用项目数据库配置(app.utils.config)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'data-crawler'))
from app.utils.config import DB_CONFIG  # noqa: E402

import pymysql  # noqa: E402

INDEX_CODE = '000688'         # 科创50
DAILY_INVEST = 300.0          # 每交易日定投金额(元)

# 止盈档位: (收益率阈值, 卖出比例, 档位名称)
TIERS = [
    (0.10, 0.30, '10%'),
    (0.15, 0.30, '15%'),
    (0.20, 1.00, '20%'),
]
REARM_THRESHOLD = 0.10        # on_dip 模式: 持仓收益率跌破该值, 三档重新装填
TRADING_DAYS_PER_YEAR = 244   # A股约每年244个交易日, 用于年化估算

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '科创50_定投止盈_回测报告.md'
)


def fetch_prices(end_date=None):
    """从 index_info 取科创50收盘价, 按交易日升序。

    end_date: 可选, 仅取 trade_date <= end_date 的数据。用于排除当天盘中未确定的
              收盘价(回测应基于已确定的交易日数据, 保证可复现)。
    """
    conn = pymysql.connect(
        host=DB_CONFIG['host'], port=DB_CONFIG['port'],
        user=DB_CONFIG['user'], password=DB_CONFIG['password'],
        database=DB_CONFIG['database'], charset=DB_CONFIG['charset'],
    )
    try:
        with conn.cursor() as cur:
            sql = ("SELECT trade_date, close_price FROM index_info "
                   "WHERE index_code=%s AND del_flag='1'")
            params = [INDEX_CODE]
            if end_date is not None:
                sql += " AND trade_date <= %s"
                params.append(end_date)
            sql += " ORDER BY trade_date"
            cur.execute(sql, params)
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

    lo, hi, mid = -0.9999, 10.0, 0.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        v = npv(mid)
        if abs(v) < 1e-6 or (hi - lo) < 1e-9:
            break
        if v > 0:
            lo = mid
        else:
            hi = mid
    return mid


def run_backtest(prices, rearm_mode='on_clear'):
    """执行回测, 返回 (events, summary)。

    rearm_mode:
      'on_clear' - 仅 20% 清仓后重装(用户选择)
      'on_dip'   - 持仓收益率跌破 10% 即重装(沪深300 V1 口径, 用于敏感性对比)
    """
    total_shares = 0.0       # 当前持仓份额
    total_cost = 0.0         # 当前持仓对应的投入成本(卖出按比例结转)
    total_invested = 0.0     # 累计定投金额
    cum_realized = 0.0       # 累计实现盈亏
    armed = {0.10: True, 0.15: True, 0.20: True}  # 三档是否装填

    events = []
    peak_profit_rate = 0.0   # 历史最高持仓收益率(观察用)
    daily_cf = []            # XIRR 现金流: (date, amount), 定投为负

    for trade_date, price in prices:
        # 1) 每日定投买入(当日收盘价)
        buy_shares = DAILY_INVEST / price
        total_shares += buy_shares
        total_cost += DAILY_INVEST
        total_invested += DAILY_INVEST
        daily_cf.append((trade_date, -DAILY_INVEST))

        # 2) 持仓收益率 = (市值 - 成本) / 成本 = (现价 - 平均成本) / 平均成本
        if total_cost > 0:
            profit_rate = (total_shares * price - total_cost) / total_cost
        else:
            profit_rate = 0.0
        if profit_rate > peak_profit_rate:
            peak_profit_rate = profit_rate

        # 3) 重装判定: on_dip 模式跌破 10% 即重装; on_clear 模式此处不重装
        if rearm_mode == 'on_dip' and profit_rate < REARM_THRESHOLD:
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

                # 20% 清仓 -> 三档重装(on_clear 的唯一重装路径; on_dip 也一致)
                if threshold == 0.20:
                    armed = {0.10: True, 0.15: True, 0.20: True}

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
                    'cost_before': cost_before,
                    'cost_after': cost_after,
                    'realized': realized,
                    'cum_realized': cum_realized,
                })
                # 比例卖出不改变平均成本, profit_rate 不变, 无需重算

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

    # XIRR: 每日定投流出 + 期末总资产(持仓市值 + 回款现金)流入
    daily_cf.append((prices[-1][0], final_value + cash))
    xirr_val = _xirr(daily_cf)

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
        'cash': cash,
        'total_profit': total_profit,
        'total_return': total_return,
        'annualized': annualized,
        'peak_profit_rate': peak_profit_rate,
        'xirr': xirr_val,
    }
    return events, summary


# ---------- 格式化辅助 ----------
def money(x):
    return f"{x:,.2f}"


def shares(x):
    return f"{x:,.4f}"


def pct(x):
    return f"{x * 100:.2f}%"


def build_report(events, summary, dip_summary):
    L = []
    s = summary
    L.append("# 科创50 每日定投 + 阶梯止盈 回测报告")
    L.append("")
    L.append("> 数据来源: `personal-finance.index_info` 表, 科创50指数(index_code=000688)日线收盘价。")
    L.append("> 回测脚本: `tasks/backtest_kc50_dca.py`。")
    L.append("")

    L.append("## 一、策略与假设")
    L.append("")
    L.append("| 项 | 设定 |")
    L.append("|---|---|")
    L.append("| 标的 | 科创50指数(000688), 以收盘价模拟可投资净值 |")
    L.append(f"| 定投 | 每个交易日投入 {money(DAILY_INVEST)} 元, 自 {s['first_date']} 起不间断(无论涨跌) |")
    L.append("| 止盈档位 | 持仓收益率 ≥10% 卖出当时持仓 30%; ≥15% 卖 30%; ≥20% 一次性卖出全部(100%) |")
    L.append("| 档位重装 | **仅 20% 清仓后重装**: 10%/15% 触发后本轮不再触发, 直到一次 20% 清仓才三档重装 |")
    L.append("| 持仓收益率 | (持仓市值 − 持仓成本) / 持仓成本, 等价于 (现价 − 平均成本) / 平均成本 |")
    L.append("| 成本结转 | 卖出按比例结转成本(平均成本法), 卖出不改变平均成本 |")
    L.append("| 每日顺序 | 先以当日收盘价定投买入, 再据当日收盘价判定止盈 |")
    L.append("| 回款处理 | 止盈回款留作现金, 不自动再投(再投列为优化方向) |")
    L.append("| 费用 | 不计交易费用、分红再投、税收; 指数点位近似可投资(可买碎额) |")
    L.append("")

    L.append("## 二、数据概览")
    L.append("")
    L.append("| 项 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 交易日数 | {s['n_days']} |")
    L.append(f"| 回测区间 | {s['first_date']} ~ {s['last_date']} |")
    L.append(f"| 收盘价区间 | {money(s['min_price'])} ~ {money(s['max_price'])} |")
    L.append(f"| 区间内最高持仓收益率 | {pct(s['peak_profit_rate'])} |")
    L.append("")

    L.append("## 三、回测汇总")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 累计定投金额 | {money(s['total_invested'])} 元 |")
    L.append(f"| 定投天数 | {s['n_days']} 个交易日 |")
    L.append(f"| 止盈次数(合计) | {s['n_events']} 次 |")
    L.append(f"| └ 10%档 | {s['tier_counts'].get('10%', 0)} 次 |")
    L.append(f"| └ 15%档 | {s['tier_counts'].get('15%', 0)} 次 |")
    L.append(f"| └ 20%档 | {s['tier_counts'].get('20%', 0)} 次 |")
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

    L.append("## 四、止盈事件明细")
    L.append("")
    L.append(f"共 {s['n_events']} 次止盈。下表逐次记录: 触发日期 / 档位 / 触发时持仓收益率 / "
             "收盘价 / 止盈前份额 / 卖出份额 / 止盈后份额 / 止盈前市值(持仓金额) / 止盈前成本 / "
             "卖出金额(止盈金额) / 止盈后市值 / 本次实现盈亏 / 累计实现盈亏。")
    L.append("")
    L.append("| # | 日期 | 档位 | 触发收益率 | 收盘价 | 止盈前份额 | 卖出份额 | 止盈后份额 | "
             "止盈前市值 | 止盈前成本 | 卖出金额 | 止盈后市值 | 本次实现盈亏 | 累计实现盈亏 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(events, 1):
        L.append(
            f"| {i} | {e['date']} | {e['tier']} | {pct(e['profit_rate'])} | {money(e['price'])} | "
            f"{shares(e['shares_before'])} | {shares(e['shares_sold'])} | {shares(e['shares_after'])} | "
            f"{money(e['value_before'])} | {money(e['cost_before'])} | {money(e['sell_proceeds'])} | "
            f"{money(e['value_after'])} | {money(e['realized'])} | {money(e['cum_realized'])} |"
        )
    L.append("")

    # 按年分布
    L.append("## 五、止盈事件按年分布")
    L.append("")
    by_year = defaultdict(lambda: {'count': 0, 'proceeds': 0.0, 'realized': 0.0})
    for e in events:
        y = e['date'].year
        by_year[y]['count'] += 1
        by_year[y]['proceeds'] += e['sell_proceeds']
        by_year[y]['realized'] += e['realized']
    L.append("| 年份 | 止盈次数 | 卖出回款(元) | 实现盈亏(元) |")
    L.append("|---|---|---|---|")
    for y in sorted(by_year):
        d = by_year[y]
        L.append(f"| {y} | {d['count']} | {money(d['proceeds'])} | {money(d['realized'])} |")
    L.append("")

    # 敏感性: 重装策略对比
    L.append("## 六、敏感性: 重装策略对比(on_clear vs on_dip)")
    L.append("")
    L.append("本回测采用用户选择的 **on_clear(仅 20% 清仓后重装)**。下表对比若改为 "
             "**on_dip(跌破 10% 即重装, 即沪深300 V1 口径)** 的差异: on_dip 会让 10% 档在"
             "多轮小级别上涨中反复触发, 止盈更频繁、回款更早, 但也可能在震荡市过早减仓、"
             "错失后续大涨。")
    L.append("")
    d = dip_summary
    L.append("| 指标 | on_clear(本报告) | on_dip(对照) | 差异 |")
    L.append("|---|---|---|---|")
    L.append(f"| 止盈次数 | {s['n_events']} | {d['n_events']} | {d['n_events']-s['n_events']:+d} |")
    L.append(f"| └ 10%档 | {s['tier_counts'].get('10%',0)} | {d['tier_counts'].get('10%',0)} | "
             f"{d['tier_counts'].get('10%',0)-s['tier_counts'].get('10%',0):+d} |")
    L.append(f"| └ 15%档 | {s['tier_counts'].get('15%',0)} | {d['tier_counts'].get('15%',0)} | "
             f"{d['tier_counts'].get('15%',0)-s['tier_counts'].get('15%',0):+d} |")
    L.append(f"| └ 20%档 | {s['tier_counts'].get('20%',0)} | {d['tier_counts'].get('20%',0)} | "
             f"{d['tier_counts'].get('20%',0)-s['tier_counts'].get('20%',0):+d} |")
    L.append(f"| 累计卖出回款 | {money(s['total_sell_proceeds'])} | {money(d['total_sell_proceeds'])} | "
             f"{money(d['total_sell_proceeds']-s['total_sell_proceeds'])} |")
    L.append(f"| 累计实现盈亏 | {money(s['cum_realized'])} | {money(d['cum_realized'])} | "
             f"{money(d['cum_realized']-s['cum_realized'])} |")
    L.append(f"| 期末持仓市值 | {money(s['final_value'])} | {money(d['final_value'])} | "
             f"{money(d['final_value']-s['final_value'])} |")
    L.append(f"| 期末总资产 | {money(s['final_value']+s['cash'])} | "
             f"{money(d['final_value']+d['cash'])} | "
             f"{money((d['final_value']+d['cash'])-(s['final_value']+s['cash']))} |")
    L.append(f"| 总收益率 | {pct(s['total_return'])} | {pct(d['total_return'])} | "
             f"{pct(d['total_return']-s['total_return'])} |")
    L.append(f"| XIRR | {pct(s['xirr'])} | {pct(d['xirr'])} | {pct(d['xirr']-s['xirr'])} |")
    L.append("")

    L.append("## 七、可优化方向")
    L.append("")
    L.append("针对科创50 **高波动、强趋势、成长风格** 的特性, 在本策略基础上可考虑:")
    L.append("")
    L.append("1. **回款再投(子弹池复利)**: 当前止盈回款闲置, 零复利。可让回款进入子弹池, "
             "在低位(如收盘价低于 250 日均线 8% 以上)加速抄底, 把高位套现的钱变成低位筹码, "
             "吃两轮大波段。沪深300 同款优化(V2)已验证可显著提升总收益。")
    L.append("2. **均线/估值加权定投**: 当前无论涨跌每日固定 300 元, 顶部照样定投抬高成本。"
             "可按收盘价相对 250 日均线的偏离度加权——低估多投、高估停投, 压低平均成本。"
             "科创50波动大于沪深300, 该优化的潜力更大。")
    L.append("3. **重装策略本身是优化杠杆**: 见第六节敏感性。on_dip 在震荡市更早止盈、"
             "提高资金周转, 但可能过早减仓; on_clear 更稳、更吃趋势。可结合波动率动态切换, "
             "或对 10% 档设冷却期(如清仓后 N 个交易日不再触发)以兼顾。")
    L.append("4. **止盈档位动态化**: 当前 10/15/20% 为固定档。可结合 PE 历史分位、波动率 "
             "动态调整——高估区提前止盈、低估区放宽阈值。注意: index_info 中科创50的 "
             "pe_ratio/pe_percentile 字段当前为 0(未采集), 落地此项需先补估值数据。")
    L.append("5. **20% 档保留底仓而非全清**: 科创50趋势性强, 全清后若继续上涨会踏空。"
             "可改为 20% 档卖出 70%、保留 30% 底仓吃趋势, 跌破均线再止剩余底仓。")
    L.append("6. **定投金额随估值/回撤调整**: 固定 300 元对资金利用不够灵活。可在低估/大回撤时"
             "加大定投(如 1.5–2 倍), 高估时减半, 进一步压低成本。")
    L.append("7. **止盈基准优化**: 当前止盈看「组合整体收益率」, 每日新增定投会持续稀释收益率, "
             "导致横盘时收益率被压低、止盈推迟。可改为按「最早批次成本」或「移动平均成本」"
             "分批止盈, 反映不同批次的真实盈亏。")
    L.append("")

    L.append("## 八、说明与风险")
    L.append("")
    L.append("- 本回测以**指数收盘价**模拟净值, 未折算基金跟踪误差、申赎费率与分红, "
             "结果略乐观于真实科创50指数基金定投。")
    L.append("- 持仓收益率为**组合层面**的(市值−成本)/成本; 每日新增定投会抬高平均成本, "
             "因此即便行情横盘, 持仓收益率也会被持续稀释。")
    L.append("- 重装规则为「仅 20% 清仓后重装」: 若一轮上涨触发了 10%/15% 却未到 20% 就回落, "
             "这两档保持已触发状态、不再卖出, 直到出现一次完整的 20% 清仓。故止盈事件偏少、"
             "集中在强势行情; 震荡市可能出现「只买不卖」的累积期。")
    L.append("- 单日涨幅足以同时穿越多档时(如跳空大涨), 10%/15%/20% 会在同一交易日依次触发, "
             "20% 档卖出全部, 净效果为清仓。")
    L.append("- 卖出按比例结转成本(平均成本法), 单次止盈不改变剩余持仓的平均成本。")
    L.append("- XIRR 为资金加权年化, 考虑 6 年陆续投入的资金时间价值, 比简单总额法更严谨; "
             "年化(244日/年)为粗略估算, 仅供参考。")
    L.append("- 本报告不构成投资建议。")
    L.append("")
    return "\n".join(L)


def main():
    prices = fetch_prices()
    if not prices:
        print("未取到科创50行情数据", file=sys.stderr)
        sys.exit(1)

    events, summary = run_backtest(prices, rearm_mode='on_clear')
    _dip_events, dip_summary = run_backtest(prices, rearm_mode='on_dip')

    report = build_report(events, summary, dip_summary)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    s = summary
    print(f"回测区间: {s['first_date']} ~ {s['last_date']} ({s['n_days']} 个交易日)")
    print(f"累计定投: {money(s['total_invested'])} 元")
    print(f"止盈次数: {s['n_events']} 次 "
          f"(10%档 {s['tier_counts'].get('10%', 0)}, "
          f"15%档 {s['tier_counts'].get('15%', 0)}, "
          f"20%档 {s['tier_counts'].get('20%', 0)})")
    print(f"累计实现盈亏: {money(s['cum_realized'])} 元 | 累计卖出回款: {money(s['total_sell_proceeds'])} 元")
    print(f"期末市值: {money(s['final_value'])} 元 | 浮动盈亏: {money(s['unrealized'])} 元 | "
          f"现金: {money(s['cash'])} 元")
    print(f"总收益: {money(s['total_profit'])} 元 | 总收益率: {pct(s['total_return'])} | "
          f"年化(估): {pct(s['annualized'])} | XIRR: {pct(s['xirr'])}")
    print(f"[敏感性 on_dip] 止盈 {dip_summary['n_events']} 次 | 总收益率: {pct(dip_summary['total_return'])} | "
          f"XIRR: {pct(dip_summary['xirr'])}")
    print(f"报告已生成: {REPORT_PATH}")


if __name__ == '__main__':
    main()
