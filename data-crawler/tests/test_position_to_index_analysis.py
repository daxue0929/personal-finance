#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓分析跳转指数分析测试（TDD）

验证 get_position_options 返回项含 index_code（关联 position 表的指数代码），
供持仓分析页「指数分析」按钮跳转传参。
"""
from unittest.mock import MagicMock

from app.storage.position_daily_snapshot_storage import PositionDailySnapshotStorage


def _make_storage_with_mock_session():
    storage = PositionDailySnapshotStorage()
    mock_session = MagicMock()
    storage.Session = MagicMock(return_value=mock_session)
    return storage, mock_session


def test_options_include_index_code():
    """返回项含 index_code（每项 4 元组：position_id, fund_code, fund_name, index_code）"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.outerjoin.return_value.distinct.return_value.order_by.return_value.all.return_value = [
        (2, '011613', '华夏科创50ETF联接C', '000688'),
        (3, '000001', '基金B', None),
    ]
    result = storage.get_position_options()
    assert result[0] == {'position_id': 2, 'fund_code': '011613', 'fund_name': '华夏科创50ETF联接C', 'index_code': '000688'}
    assert result[1]['index_code'] is None
    assert result[1]['fund_name'] == '基金B'


def test_empty_returns_empty_list():
    """无快照返回 []"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.outerjoin.return_value.distinct.return_value.order_by.return_value.all.return_value = []
    assert storage.get_position_options() == []
