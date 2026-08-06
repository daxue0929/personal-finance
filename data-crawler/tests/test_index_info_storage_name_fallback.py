#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index_info insert 分支 name 4 道兜底优先级测试（TDD）

配套功能：PRD "index-basic-table" §AC-2 T2.8
修复 2026-08-05 index_info.index_name 丢失 bug 的根因。

优先级：
1. index_data['index_name']（入参直接传）
2. IndexBasicStorage.get(index_code).index_name（DB 元表真源）
3. KcIndexParser.INDEX_NAME_MAP.get(index_code, '')（parser 兜底）
4. 历史 index_info 最近一条非空 name（原兜底保留）
5. ''

每道独立 try/except，失败降级到下一道。
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest


# ==================== 优先级 1：入参 name 优先 ====================

def test_uses_index_data_name_when_provided():
    """入参 index_name 非空时，优先用入参，不查 DB / parser / 历史"""
    from app.storage.index_info_storage import IndexInfoStorage

    storage = IndexInfoStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session

    # query: 不存在历史
    mock_session.query.return_value.filter.return_value.first.return_value = None

    data = {
        'index_code': '000300',
        'index_name': '沪深300',  # 入参
        'trade_date': date(2026, 8, 6),
        'open_price': 4500.0,
        'close_price': 4600.0,
        'change_percent': 1.5,
    }

    # mock 各层兜底都不应被访问
    with patch('app.storage.index_basic_storage.IndexBasicStorage') as mock_basic_cls, \
         patch('app.parser.kc_index_parser.KcIndexParser') as mock_parser_cls:
        mock_basic_cls.return_value.get.return_value = MagicMock(index_name='SHOULD_NOT_USE')
        result = storage.create_or_update_index_info(data)

    assert result is True
    # 入参 name 用了
    added_row = mock_session.add.call_args.args[0]
    assert added_row.index_name == '沪深300'
    # IndexBasicStorage 不该被查（入参已有 name）
    mock_basic_cls.return_value.get.assert_not_called()


# ==================== 优先级 2：入参空 → 查 index_basic ====================

def test_falls_back_to_index_basic_when_no_index_data_name():
    """入参 name 为空，IndexBasicStorage.get(code).index_name 非空时用 DB 元表"""
    from app.storage.index_info_storage import IndexInfoStorage

    storage = IndexInfoStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None

    with patch('app.storage.index_basic_storage.IndexBasicStorage') as mock_basic_cls:
        mock_basic_cls.return_value.get.return_value = MagicMock(index_name='沪深300_元表')

        data = {
            'index_code': '000300',
            # 没有 index_name
            'trade_date': date(2026, 8, 6),
            'open_price': 4500.0,
            'close_price': 4600.0,
        }
        result = storage.create_or_update_index_info(data)

    assert result is True
    added_row = mock_session.add.call_args.args[0]
    assert added_row.index_name == '沪深300_元表'
    mock_basic_cls.return_value.get.assert_called_once_with('000300')


# ==================== 优先级 3：index_basic 也没有 → 查 INDEX_NAME_MAP ====================

def test_falls_back_to_parser_map_when_no_index_basic():
    """IndexBasicStorage 查不到（get 返 None 或抛异常）→ 用 parser INDEX_NAME_MAP"""
    from app.storage.index_info_storage import IndexInfoStorage

    storage = IndexInfoStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None

    with patch('app.storage.index_basic_storage.IndexBasicStorage') as mock_basic_cls, \
         patch('app.parser.kc_index_parser.KcIndexParser') as mock_parser_cls:
        # index_basic 查不到
        mock_basic_cls.return_value.get.return_value = None
        # parser INDEX_NAME_MAP 返值
        mock_parser_cls.INDEX_NAME_MAP = {'000300': '沪深300_兜底'}

        data = {
            'index_code': '000300',
            'trade_date': date(2026, 8, 6),
            'open_price': 4500.0,
        }
        result = storage.create_or_update_index_info(data)

    assert result is True
    added_row = mock_session.add.call_args.args[0]
    assert added_row.index_name == '沪深300_兜底'


def test_falls_back_to_parser_map_when_index_basic_raises():
    """IndexBasicStorage.get 抛异常时降级到 INDEX_NAME_MAP（每道独立 try/except）"""
    from app.storage.index_info_storage import IndexInfoStorage

    storage = IndexInfoStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None

    with patch('app.storage.index_basic_storage.IndexBasicStorage') as mock_basic_cls, \
         patch('app.parser.kc_index_parser.KcIndexParser') as mock_parser_cls:
        mock_basic_cls.return_value.get.side_effect = Exception("DB 炸了")
        mock_parser_cls.INDEX_NAME_MAP = {'000300': '沪深300_降级'}

        data = {
            'index_code': '000300',
            'trade_date': date(2026, 8, 6),
            'open_price': 4500.0,
        }
        result = storage.create_or_update_index_info(data)

    assert result is True
    added_row = mock_session.add.call_args.args[0]
    assert added_row.index_name == '沪深300_降级'


# ==================== 优先级 4：parser map 也没有 → 查历史 index_info ====================

def test_falls_back_to_history_when_no_parser_map():
    """INDEX_NAME_MAP 没有该 code → 用历史 index_info 最近一条非空 name"""
    from app.storage.index_info_storage import IndexInfoStorage

    storage = IndexInfoStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None

    with patch('app.storage.index_basic_storage.IndexBasicStorage') as mock_basic_cls, \
         patch('app.parser.kc_index_parser.KcIndexParser') as mock_parser_cls:
        mock_basic_cls.return_value.get.return_value = None
        mock_parser_cls.INDEX_NAME_MAP = {}  # 没有 000300

        data = {
            'index_code': '000300',
            'trade_date': date(2026, 8, 6),
            'open_price': 4500.0,
        }
        # 历史查到的最近一条 name
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = ('沪深300_历史',)

        result = storage.create_or_update_index_info(data)

    assert result is True
    added_row = mock_session.add.call_args.args[0]
    assert added_row.index_name == '沪深300_历史'


# ==================== 优先级 5：所有都没有 → 空串 ====================

def test_returns_empty_when_all_unavailable():
    """所有 4 道都没有 → 返回空串（不抛异常）"""
    from app.storage.index_info_storage import IndexInfoStorage

    storage = IndexInfoStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None
    # 历史查不到
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    with patch('app.storage.index_basic_storage.IndexBasicStorage') as mock_basic_cls, \
         patch('app.parser.kc_index_parser.KcIndexParser') as mock_parser_cls:
        mock_basic_cls.return_value.get.return_value = None
        mock_parser_cls.INDEX_NAME_MAP = {}

        data = {
            'index_code': '999999',  # 未知 code
            'trade_date': date(2026, 8, 6),
            'open_price': 4500.0,
        }
        result = storage.create_or_update_index_info(data)

    assert result is True
    added_row = mock_session.add.call_args.args[0]
    assert added_row.index_name == ''
