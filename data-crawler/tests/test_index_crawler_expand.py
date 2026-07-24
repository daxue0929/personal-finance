#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数爬虫扩展测试（TDD）

验证：
1. KcIndexParser 支持 000300(沪深300,sh) / 399673(创业板50,sz)，URL 用 market 前缀（不再写死 sh）。
2. index_fetch_helper.fetch_and_store_index 抓取+入库逻辑（mock parser/storage）。
"""
import pytest
from unittest.mock import MagicMock, patch

from app.parser.kc_index_parser import KcIndexParser, KcIndexData


# ==================== Parser: market + URL 前缀 ====================

def test_index_config_contains_new_indexes():
    """INDEX_CONFIG 含沪深300(sh) 与创业板50(sz)，且带 market 字段"""
    assert '000300' in KcIndexParser.INDEX_CONFIG
    assert KcIndexParser.INDEX_CONFIG['000300']['market'] == 'sh'
    assert '399673' in KcIndexParser.INDEX_CONFIG
    assert KcIndexParser.INDEX_CONFIG['399673']['market'] == 'sz'


def test_parser_hs300_uses_sh_prefix():
    """沪深300 用 sh 前缀"""
    p = KcIndexParser('000300')
    assert p.market == 'sh'
    url = p.TENCENT_URL.format(market=p.market, index_code=p.index_code)
    assert url == 'https://qt.gtimg.cn/q=sh000300'


def test_parser_cyb50_uses_sz_prefix():
    """创业板50 用 sz 前缀（深圳）"""
    p = KcIndexParser('399673')
    assert p.market == 'sz'
    url = p.TENCENT_URL.format(market=p.market, index_code=p.index_code)
    assert url == 'https://qt.gtimg.cn/q=sz399673'


def test_parser_existing_kc50_still_sh():
    """现有科创50 仍为 sh"""
    p = KcIndexParser('000688')
    assert p.market == 'sh'


def test_parser_unsupported_code_raises():
    """不支持代码仍 raise ValueError（回归保护）"""
    with pytest.raises(ValueError):
        KcIndexParser('999999')


# ==================== Helper: fetch_and_store_index ====================

def _fake_index_data(code='000300', name='沪深300'):
    return KcIndexData(
        index_code=code, index_name=name,
        open_price=4600.0, close_price=4649.19, high_price=4728.0, low_price=4580.0,
        change_percent=-1.67, volume=10000.0, amount=200.0,
        turnover_rate=0.0, pe_ratio=14.37, pb_ratio=0.0,
        update_time='2026-07-24 15:00:00'
    )


@patch('app.task.index_fetch_helper.KcIndexParser')
@patch('app.task.index_fetch_helper.IndexInfoStorage')
def test_fetch_and_store_index_success(mock_storage_cls, mock_parser_cls):
    """force_run 时拉取并入库，dict 含 index_type/source，返回 KcIndexData"""
    from app.task.index_fetch_helper import fetch_and_store_index
    mock_parser_cls.return_value.fetch.return_value = _fake_index_data()
    mock_storage = mock_storage_cls.return_value

    result = fetch_and_store_index('000300', force_run=True)

    assert isinstance(result, KcIndexData)
    assert result.index_code == '000300'
    mock_parser_cls.assert_called_once_with('000300')
    mock_storage.create_or_update_index_info.assert_called_once()
    data = mock_storage.create_or_update_index_info.call_args[0][0]
    assert data['index_code'] == '000300'
    assert data['index_name'] == '沪深300'
    assert data['index_type'] == '宽基指数'
    assert data['source'] == '腾讯财经'


@patch('app.task.index_fetch_helper.is_trading_time', return_value=False)
@patch('app.task.index_fetch_helper.KcIndexParser')
@patch('app.task.index_fetch_helper.IndexInfoStorage')
def test_fetch_and_store_index_skip_non_trading(mock_storage_cls, mock_parser_cls, _):
    """非交易时段且非 force_run：跳过，不拉取不入库"""
    from app.task.index_fetch_helper import fetch_and_store_index
    result = fetch_and_store_index('000300', force_run=False)
    assert result is None
    mock_parser_cls.assert_not_called()
    mock_storage_cls.assert_not_called()


@patch('app.task.index_fetch_helper.KcIndexParser')
@patch('app.task.index_fetch_helper.IndexInfoStorage')
def test_fetch_and_store_index_no_data(mock_storage_cls, mock_parser_cls):
    """fetch 返回 None：不入库，返回 None"""
    from app.task.index_fetch_helper import fetch_and_store_index
    mock_parser_cls.return_value.fetch.return_value = None
    mock_storage = mock_storage_cls.return_value

    result = fetch_and_store_index('000300', force_run=True)

    assert result is None
    mock_storage.create_or_update_index_info.assert_not_called()


@patch('app.task.index_fetch_helper.get_beijing_now')
def test_is_trading_time(mock_now):
    """交易时段判断：周末 False、周一盘中 True、周一盘前 False"""
    import datetime
    from app.task.index_fetch_helper import is_trading_time
    mock_now.return_value = datetime.datetime(2026, 7, 25, 10, 0)  # 周六
    assert is_trading_time() is False
    mock_now.return_value = datetime.datetime(2026, 7, 27, 10, 0)  # 周一 10:00
    assert is_trading_time() is True
    mock_now.return_value = datetime.datetime(2026, 7, 27, 8, 0)   # 周一 8:00
    assert is_trading_time() is False
