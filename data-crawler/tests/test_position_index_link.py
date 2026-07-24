#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓关联指数（index_code）透传测试（TDD）

验证 PositionStorage 对 index_code 字段的增/查/改透传：
- create_position：传入 index_code 时写入 Position 对象
- create_position：index_code 缺省时不报错
- get_position_by_id：返回 dict 含 index_code
- get_positions_with_pagination：返回 dict 含 index_code
- update_position：透传 index_code（hasattr 通用循环 + 模型新列）

测试通过 mock SQLAlchemy session，绝不连真实库（.env 指生产库）。
"""
from datetime import date
from unittest.mock import MagicMock

from app.storage.position_storage import PositionStorage, Position


def _make_storage_with_mock_session():
    """构造 PositionStorage，把 get_session 替换为返回 mock session"""
    storage = PositionStorage()
    mock_session = MagicMock()
    storage.Session = MagicMock(return_value=mock_session)
    return storage, mock_session


def _make_position(**overrides):
    """构造一个带默认值的 Position 实例（不落库）"""
    pos = Position()
    pos.id = 1
    pos.fund_code = '001001'
    pos.fund_name = '测试基金'
    pos.shares = 100
    pos.cost_price = 1.5
    pos.current_price = 2.0
    pos.current_value = 200.0
    pos.cost_amount = 150.0
    pos.profit_loss = 50.0
    pos.profit_loss_rate = 33.33
    pos.buy_date = date(2026, 1, 1)
    pos.remark = ''
    pos.create_time = None
    pos.update_time = None
    pos.index_code = '000300'
    for k, v in overrides.items():
        setattr(pos, k, v)
    return pos


# ==================== create_position ====================

def test_create_position_passes_index_code():
    """create_position 传入 index_code 时，写入 Position 对象"""
    storage, mock_session = _make_storage_with_mock_session()
    data = {
        'fund_code': '001001', 'fund_name': '测试基金',
        'shares': 100, 'cost_price': 1.5, 'current_price': 2.0,
        'buy_date': '2026-01-01', 'index_code': '000300',
    }
    storage.create_position(data)
    assert mock_session.add.called
    added = mock_session.add.call_args[0][0]
    assert isinstance(added, Position)
    assert added.index_code == '000300'
    assert mock_session.commit.called


def test_create_position_index_code_optional():
    """index_code 缺省时不报错，且 Position.index_code 为 None"""
    storage, mock_session = _make_storage_with_mock_session()
    data = {
        'fund_code': '001001', 'shares': 100,
        'cost_price': 1.5, 'current_price': 2.0, 'buy_date': '2026-01-01',
    }
    storage.create_position(data)  # 不传 index_code
    added = mock_session.add.call_args[0][0]
    assert added.index_code is None


# ==================== 查询返回 dict ====================

def test_get_position_by_id_returns_index_code():
    """get_position_by_id 返回 dict 含 index_code"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.filter.return_value.first.return_value = _make_position()
    result = storage.get_position_by_id(1)
    assert result is not None
    assert result['index_code'] == '000300'


def test_get_positions_with_pagination_returns_index_code():
    """get_positions_with_pagination 返回 dict 含 index_code"""
    storage, mock_session = _make_storage_with_mock_session()
    q = mock_session.query.return_value.filter.return_value
    q.count.return_value = 1
    q.offset.return_value.limit.return_value.all.return_value = [_make_position()]
    result, total = storage.get_positions_with_pagination()
    assert total == 1
    assert result[0]['index_code'] == '000300'


# ==================== update_position ====================

def test_update_position_sets_index_code():
    """update_position 透传 index_code（hasattr 通用循环 + 模型新列）"""
    storage, mock_session = _make_storage_with_mock_session()
    # 不预设 index_code，验证 hasattr 反映模型新列
    pos = Position()
    pos.id = 1
    mock_session.query.return_value.filter.return_value.first.return_value = pos
    ok = storage.update_position(1, {'index_code': '000300'})
    assert ok is True
    assert pos.index_code == '000300'
    assert mock_session.commit.called
