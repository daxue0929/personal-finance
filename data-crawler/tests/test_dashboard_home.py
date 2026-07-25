#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard 首页数据源测试（TDD）

验证 PositionStorage.get_all_active_positions：全量有效持仓（含 current_value），
供 Dashboard 实时持仓占比饼图（calc_position_allocation 消费）。
"""
from unittest.mock import MagicMock

from app.storage.position_storage import PositionStorage, Position


def _make_storage_with_mock_session():
    storage = PositionStorage()
    mock_session = MagicMock()
    storage.Session = MagicMock(return_value=mock_session)
    return storage, mock_session


def _make_position(**overrides):
    p = Position()
    p.id = 1
    p.fund_code = '011613'
    p.fund_name = '华夏科创50ETF联接C'
    p.current_value = 9111.00
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def test_returns_active_positions_with_current_value():
    """返回全量有效持仓 dict，含 fund_code/fund_name/current_value"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.filter.return_value.all.return_value = [
        _make_position(),
        _make_position(id=2, fund_code='000001', fund_name='基金B', current_value=2000.0),
    ]
    result = storage.get_all_active_positions()
    assert len(result) == 2
    assert result[0]['fund_code'] == '011613'
    assert result[0]['fund_name'] == '华夏科创50ETF联接C'
    assert result[0]['current_value'] == 9111.00
    assert result[1]['current_value'] == 2000.0


def test_empty_returns_empty_list():
    """无持仓返回 []"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    assert storage.get_all_active_positions() == []


def test_current_value_none_defaults_zero():
    """current_value 为 None -> 0.0（不报错）"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.filter.return_value.all.return_value = [
        _make_position(current_value=None),
    ]
    result = storage.get_all_active_positions()
    assert result[0]['current_value'] == 0.0
