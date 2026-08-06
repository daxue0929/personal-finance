#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数基础表 Storage 层测试（TDD）

mock Session 避免连真实库（遵循 test_index_api.py 范式），验证 IndexBasicStorage 的：
- 列表查询过滤（enabled/del_flag）
- 单条 get
- create 字段验证（market / index_code 格式）
- update 白名单（index_code 不可改）
- soft_delete 软删行为
- toggle_enabled 启停

不依赖数据库，纯单元测试。
"""
from unittest.mock import MagicMock, call

import pytest


@pytest.fixture
def storage():
    """构造 IndexBasicStorage 并 mock 其 Session 工厂"""
    from app.storage.index_basic_storage import IndexBasicStorage
    s = IndexBasicStorage()
    s.Session = MagicMock()  # Session() 返回 mock session
    return s


def _make_mock_session(storage, query_results):
    """helper：让 storage.Session() 返回一个 mock session，
    query(IndexBasic).filter(...).first()/.all() 返 query_results"""
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    # query chain: .query(IndexBasic).filter(...).first() -> first result
    #             .query(IndexBasic).filter(...).all()   -> all results
    # 因为 first() 和 all() 是同 chain 的不同 terminal，配置成 first=query_results[0], all=query_results
    mock_session.query.return_value.filter.return_value.first.return_value = (
        query_results[0] if query_results else None
    )
    mock_session.query.return_value.filter.return_value.all.return_value = query_results
    return mock_session


# ==================== 列表查询 ====================

def test_list_enabled_only_returns_enabled(storage):
    """list_enabled() 调 Session，filter 链里包含 enabled=1 和 del_flag='1'"""
    from app.storage.index_basic_storage import IndexBasicStorage
    mock_session = _make_mock_session(storage, [])

    result = storage.list_enabled()

    assert result == []
    # Session 被调用（创建了一次 session）
    assert storage.Session.called
    # query 被调用
    mock_session.query.assert_called()


def test_list_all_returns_paginated_tuple(storage):
    """list_all() 返 (rows, total) tuple，参数透传"""
    mock_session = _make_mock_session(storage, [])

    result = storage.list_all(include_disabled=True, page=2, page_size=10)

    # 返 tuple
    assert isinstance(result, tuple)
    assert len(result) == 2
    # Session 被调用
    assert storage.Session.called


def test_list_all_with_filter_passes_through(storage):
    """list_all(index_code='000300') 透传过滤参数"""
    mock_session = _make_mock_session(storage, [])

    storage.list_all(index_code='000300', index_type='宽基指数')

    assert storage.Session.called
    mock_session.query.assert_called()


def test_list_all_invalid_page_clamped(storage):
    """page<=0 被 clamp 到 1（不抛异常）"""
    mock_session = _make_mock_session(storage, [])

    # page=0 / 负数不抛异常
    storage.list_all(page=0)
    storage.list_all(page=-5)

    assert storage.Session.called


def test_list_all_page_size_clamped_to_100(storage):
    """page_size > 100 被截断到 100（不抛异常）"""
    mock_session = _make_mock_session(storage, [])

    storage.list_all(page_size=999)

    assert storage.Session.called


# ==================== update enabled 值域校验 ====================

def test_update_validates_enabled_value_invalid(storage):
    """update 时 enabled=2 应 raise ValueError"""
    from app.storage.index_basic_storage import IndexBasicStorage
    existing = MagicMock()
    existing.index_code = '000300'
    existing.index_name = '沪深300'
    existing.enabled = 1
    mock_session = _make_mock_session(storage, [existing])

    with pytest.raises(ValueError, match="enabled"):
        storage.update('000300', {'enabled': 2})


def test_update_validates_enabled_string_raises(storage):
    """update 时 enabled='abc' 应 raise ValueError"""
    from app.storage.index_basic_storage import IndexBasicStorage
    existing = MagicMock()
    existing.index_code = '000300'
    existing.index_name = '沪深300'
    mock_session = _make_mock_session(storage, [existing])

    with pytest.raises(ValueError, match="enabled"):
        storage.update('000300', {'enabled': 'abc'})


def test_update_validates_enabled_value_valid_0_1(storage):
    """update 时 enabled=0 或 1 不应 raise"""
    from app.storage.index_basic_storage import IndexBasicStorage
    existing = MagicMock()
    existing.index_code = '000300'
    existing.enabled = 1
    mock_session = _make_mock_session(storage, [existing])

    # enabled=0
    result = storage.update('000300', {'enabled': 0})
    assert result is True
    # enabled=1
    result = storage.update('000300', {'enabled': 1})
    assert result is True


# ==================== get 单条 ====================

def test_get_returns_none_for_missing(storage):
    """get('999999') 不存在时返 None"""
    mock_session = _make_mock_session(storage, [None])

    result = storage.get('999999')

    assert result is None


def test_get_returns_row_when_exists(storage):
    """get('000300') 存在时返该行"""
    fake_row = MagicMock()
    fake_row.index_code = '000300'
    fake_row.index_name = '沪深300'
    mock_session = _make_mock_session(storage, [fake_row])

    result = storage.get('000300')

    assert result is fake_row
    assert result.index_name == '沪深300'


# ==================== create 字段验证 ====================

def test_create_validates_market_invalid(storage):
    """create 时 market='xx' 应 raise ValueError"""
    with pytest.raises(ValueError, match="market"):
        storage.create({
            'index_code': '000300',
            'market': 'xx',
            'index_name': '沪深300',
        })


def test_create_validates_market_valid_sh_sz(storage):
    """create 时 market='sh' 或 'sz' 不应 raise（其他流程允许）"""
    mock_session = _make_mock_session(storage, [])

    # market='sh' 不应 raise
    storage.create({
        'index_code': '000300',
        'market': 'sh',
        'index_name': '沪深300',
    })

    # market='sz' 不应 raise
    storage.create({
        'index_code': '399673',
        'market': 'sz',
        'index_name': '创业板50',
    })


def test_create_validates_index_code_length_short(storage):
    """create 时 index_code 长度 < 6 应 raise"""
    with pytest.raises(ValueError, match="index_code"):
        storage.create({
            'index_code': '12345',
            'market': 'sh',
            'index_name': '某指数',
        })


def test_create_validates_index_code_length_long(storage):
    """create 时 index_code 长度 > 6 应 raise"""
    with pytest.raises(ValueError, match="index_code"):
        storage.create({
            'index_code': '1234567',
            'market': 'sh',
            'index_name': '某指数',
        })


def test_create_validates_index_code_non_digit(storage):
    """create 时 index_code 含非数字应 raise"""
    with pytest.raises(ValueError, match="index_code"):
        storage.create({
            'index_code': '00030A',
            'market': 'sh',
            'index_name': '某指数',
        })


# ==================== update 白名单 ====================

def test_update_changes_name_only(storage):
    """update 时白名单外的字段（如 index_code）被忽略"""
    # mock 现有行
    existing = MagicMock()
    existing.index_code = '000300'
    existing.index_name = '沪深300'
    mock_session = _make_mock_session(storage, [existing])

    # 试图改 index_code 和 market，都应在白名单外
    result = storage.update('000300', {
        'index_code': '999999',  # 主键，不应改
        'market': 'sz',           # 业务不变量，不应改
        'index_name': '沪深300指数',  # 白名单内，应改
    })

    # 调用成功
    assert result is True
    # index_name 改了
    assert existing.index_name == '沪深300指数'
    # index_code 没被改（白名单过滤）
    assert existing.index_code == '000300'


# ==================== soft_delete ====================

def test_soft_delete_keeps_row(storage):
    """soft_delete 只置 del_flag='0'，不删行（index_info 历史保留）"""
    existing = MagicMock()
    existing.index_code = '000300'
    existing.del_flag = '1'
    mock_session = _make_mock_session(storage, [existing])

    result = storage.soft_delete('000300')

    assert result is True
    assert existing.del_flag == '0'  # 置为 0
    # session.commit() 被调用（持久化）
    mock_session.commit.assert_called()


def test_soft_delete_missing_returns_false(storage):
    """soft_delete 不存在的 code 返 False"""
    mock_session = _make_mock_session(storage, [None])

    result = storage.soft_delete('999999')

    assert result is False


# ==================== toggle_enabled ====================

def test_toggle_enabled_changes_flag(storage):
    """toggle_enabled(0) 改 enabled=0；toggle_enabled(1) 改 enabled=1"""
    existing = MagicMock()
    existing.index_code = '000300'
    existing.enabled = 1
    mock_session = _make_mock_session(storage, [existing])

    # 关停
    result = storage.toggle_enabled('000300', False)
    assert result is True
    assert existing.enabled == 0

    # 重启
    result = storage.toggle_enabled('000300', True)
    assert result is True
    assert existing.enabled == 1


def test_toggle_enabled_missing_returns_false(storage):
    """toggle_enabled 不存在的 code 返 False"""
    mock_session = _make_mock_session(storage, [None])

    result = storage.toggle_enabled('999999', False)

    assert result is False
