#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓分析纯计算函数

所有函数不依赖数据库，仅做数值计算，便于单元测试。
输入约定：
- snapshots：单持仓的快照序列，按 snapshot_date 升序（调用方保证）
  每项为 dict，含 snapshot_date / current_value / profit_loss / profit_loss_rate
- allocation 输入：某日全部持仓快照列表，每项含 fund_code / fund_name / current_value
- 数值字段可为 int/float/Decimal，内部统一转 float
"""
from typing import List, Optional, Dict, Any


def _f(v) -> float:
    """转 float（兼容 Decimal / None）"""
    return float(v) if v is not None else 0.0


def calc_max_drawdown(values: List) -> Optional[float]:
    """最大回撤率（百分比数值）。

    遍历市值序列，维护历史峰值，回撤 = (peak - current) / peak × 100，
    取最大回撤幅度（正数表示跌幅，如 25.0 表示回撤 25%）。

    :param values: 市值序列（按日期升序）
    :return: 最大回撤率（正数，0.0 表示无回撤）；空序列或单点返回 None
    """
    if not values or len(values) < 2:
        return None
    peak = _f(values[0])
    max_dd = 0.0
    for v in values[1:]:
        cur = _f(v)
        if cur > peak:
            peak = cur
        if peak > 0:
            dd = (peak - cur) / peak * 100
            if dd > max_dd:
                max_dd = dd
    return round(max_dd, 2)


def calc_position_overview(snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """单持仓区间概览。

    :param snapshots: 单持仓快照序列（按日期升序）
    :return: {count, start_date, end_date, latest_value, latest_profit_loss,
              latest_profit_loss_rate, max_value, min_value, max_drawdown,
              value_change, profit_loss_change}
              空序列返回 {count: 0}；单点 max_drawdown 为 None
    """
    if not snapshots:
        return {'count': 0}

    values = [_f(s.get('current_value')) for s in snapshots]
    first = snapshots[0]
    latest = snapshots[-1]

    return {
        'count': len(snapshots),
        'start_date': str(first.get('snapshot_date')),
        'end_date': str(latest.get('snapshot_date')),
        'latest_value': _f(latest.get('current_value')),
        'latest_profit_loss': _f(latest.get('profit_loss')),
        'latest_profit_loss_rate': _f(latest.get('profit_loss_rate')),
        'max_value': max(values),
        'min_value': min(values),
        'max_drawdown': calc_max_drawdown(values),
        'value_change': round(_f(latest.get('current_value')) - _f(first.get('current_value')), 2),
        'profit_loss_change': round(_f(latest.get('profit_loss')) - _f(first.get('profit_loss')), 2),
    }


def calc_position_allocation(position_snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """持仓占比（饼图数据）。

    :param position_snapshots: 某日全部持仓快照，每项含 fund_code/fund_name/current_value
    :return: [{fund_code, fund_name, value, percent}]，按占比降序，percent 为 0-100
             总市值为 0 时各 percent 为 0.0，不除零
    """
    if not position_snapshots:
        return []
    items = [
        {
            'fund_code': s.get('fund_code'),
            'fund_name': s.get('fund_name') or '',
            'value': _f(s.get('current_value')),
        }
        for s in position_snapshots
    ]
    total = sum(it['value'] for it in items)
    for it in items:
        it['percent'] = round(it['value'] / total * 100, 2) if total > 0 else 0.0
    # 按占比降序
    items.sort(key=lambda x: x['percent'], reverse=True)
    return items


def calc_portfolio_profit_series(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """累计收益序列：将快照行（单持仓序列或组合级聚合行）转为每日盈亏序列。

    输入约定：rows 每项含 snapshot_date / profit_loss（数值或 Decimal），可乱序。
    组合级时调用方需先按 snapshot_date 聚合 SUM（后端 SQL 完成）；本函数仅做映射+排序。

    :return: [{snapshot_date, profit_loss}]，按日期升序；空输入返回 []
    """
    if not rows:
        return []
    items = [
        {'snapshot_date': str(r.get('snapshot_date')), 'profit_loss': _f(r.get('profit_loss'))}
        for r in rows
    ]
    items.sort(key=lambda x: x['snapshot_date'])
    return items


def calc_portfolio_overview(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """组合级区间概览（基于聚合后的每日总市值/总盈亏序列）。

    与单持仓概览同口径，但输入为组合级聚合行，每项含
    snapshot_date / current_value / cost_amount / profit_loss。

    :return: {count, start_date, end_date, latest_value, latest_profit_loss,
              latest_profit_loss_rate, max_value, min_value, max_drawdown,
              value_change, profit_loss_change}
              空序列返回 {count: 0}；单点 max_drawdown 为 None
    """
    if not rows:
        return {'count': 0}

    sorted_rows = sorted(rows, key=lambda r: str(r.get('snapshot_date')))
    values = [_f(r.get('current_value')) for r in sorted_rows]
    first = sorted_rows[0]
    latest = sorted_rows[-1]

    # 组合级最新盈亏率 = 最新总盈亏 / 最新总成本 × 100
    latest_cost = _f(latest.get('cost_amount'))
    latest_pl = _f(latest.get('profit_loss'))
    latest_rate = round(latest_pl / latest_cost * 100, 2) if latest_cost > 0 else 0.0

    return {
        'count': len(sorted_rows),
        'start_date': str(first.get('snapshot_date')),
        'end_date': str(latest.get('snapshot_date')),
        'latest_value': _f(latest.get('current_value')),
        'latest_profit_loss': latest_pl,
        'latest_profit_loss_rate': latest_rate,
        'max_value': max(values),
        'min_value': min(values),
        'max_drawdown': calc_max_drawdown(values),
        'value_change': round(_f(latest.get('current_value')) - _f(first.get('current_value')), 2),
        'profit_loss_change': round(_f(latest.get('profit_loss')) - _f(first.get('profit_loss')), 2),
    }
