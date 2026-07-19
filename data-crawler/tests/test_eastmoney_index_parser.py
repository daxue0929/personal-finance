#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富指数抓取解析器测试（TDD）

覆盖：
1. app/parser/index_parser_base.py - BaseIndexParser 抽象基类契约、IndexData dataclass
2. app/parser/eastmoney_index_parser.py - _parse 纯函数（喂渲染后 HTML fixture，覆盖 A/HK/US 字段缺失）+ fetch（mock PlaywrightClient）
3. app/task/fetch_eastmoney_index_task.py - 市场门控、trade_date 时区、task 编排

测试用构造的渲染后 HTML fixture（基于用户提供的真实页面结构），不触网。
"""
import os
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), 'r', encoding='utf-8') as f:
        return f.read()


# ==================== 基类 BaseIndexParser / IndexData ====================

def test_base_parser_cannot_instantiate():
    """BaseIndexParser 是抽象基类，不能直接实例化"""
    from app.parser.index_parser_base import BaseIndexParser
    with pytest.raises(TypeError):
        BaseIndexParser()


def test_subclass_must_implement_abstract_methods():
    """子类必须实现 _fetch_html 和 _parse"""
    from app.parser.index_parser_base import BaseIndexParser

    class OnlyFetch(BaseIndexParser):
        def _fetch_html(self, index_code):
            return None
    with pytest.raises(TypeError):
        OnlyFetch()

    class OnlyParse(BaseIndexParser):
        def _parse(self, html, index_code):
            return None
    with pytest.raises(TypeError):
        OnlyParse()

    class Complete(BaseIndexParser):
        def _fetch_html(self, index_code):
            return '<html></html>'
        def _parse(self, html, index_code):
            return None
    assert Complete() is not None


def test_index_data_fields():
    """IndexData dataclass 字段完整"""
    from app.parser.index_parser_base import IndexData
    d = IndexData(
        index_code='000300', index_name='沪深300', index_type='宽基指数',
        trade_date='2026-07-18', open_price=3452.78, close_price=3416.88,
        high_price=3503.00, low_price=3392.37, change_percent=-1.20,
        volume=2302.0, amount=521.1, turnover_rate=1.87, update_time='')
    assert d.index_code == '000300'
    assert d.close_price == 3416.88
    assert d.volume == 2302.0


def test_base_fetch_returns_none_on_exception():
    """_fetch_html 异常时 fetch 返回 None"""
    from app.parser.index_parser_base import BaseIndexParser

    class Boom(BaseIndexParser):
        def _fetch_html(self, index_code):
            raise Exception('network boom')
        def _parse(self, html, index_code):
            return None
    assert Boom().fetch('000300') is None


def test_base_fetch_returns_none_when_html_empty():
    """_fetch_html 返回 None/空时 fetch 返回 None（不调 _parse）"""
    from app.parser.index_parser_base import BaseIndexParser

    class Empty(BaseIndexParser):
        def _fetch_html(self, index_code):
            return None
        def _parse(self, html, index_code):
            raise AssertionError('不应调用 _parse')
    assert Empty().fetch('000300') is None


# ==================== EastmoneyIndexParser._parse 纯函数 ====================

def test_parse_a_index_full_fields():
    """_parse 喂 A 股全字段 HTML，解析正确"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    html = _load_fixture('eastmoney_000300.html')
    data = EastmoneyIndexParser()._parse(html, '000300')
    assert data is not None
    assert data.index_code == '000300'
    assert data.close_price == 3416.88   # .zxj
    assert data.open_price == 3452.78    # 今开
    assert data.high_price == 3503.00    # 最高
    assert data.low_price == 3392.37     # 最低
    assert data.change_percent == -1.20  # 涨跌幅 去%
    assert data.volume == 2302.0         # 成交量 去"万手"
    assert data.amount == 521.1          # 成交额 去"亿"
    assert data.turnover_rate == 1.87    # 换手 去%


def test_parse_hk_index_missing_turnover():
    """_parse 喂 HK fixture，换手为 - -> 0.0"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    html = _load_fixture('eastmoney_HSTECH.html')
    data = EastmoneyIndexParser()._parse(html, 'HSTECH')
    assert data is not None
    assert data.close_price == 4623.17
    assert data.turnover_rate == 0.0   # 换手 -
    assert data.amount == 1155.0       # 成交额 1155亿


def test_parse_us_index_missing_amount_turnover():
    """_parse 喂 US fixture，成交额+换手为 - -> 0.0"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    html = _load_fixture('eastmoney_NDX.html')
    data = EastmoneyIndexParser()._parse(html, 'NDX')
    assert data is not None
    assert data.close_price == 25520.24
    assert data.amount == 0.0          # 成交额 -
    assert data.turnover_rate == 0.0   # 换手 -
    assert data.volume == 0.0          # 成交量 -


def test_parse_empty_html_returns_none():
    """空 HTML 返回 None"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    assert EastmoneyIndexParser()._parse('', '000300') is None


def test_parse_no_brief_info_returns_none():
    """HTML 无 .brief_info 返回 None"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    html = '<html><body>无关内容</body></html>'
    assert EastmoneyIndexParser()._parse(html, '000300') is None


# ==================== EastmoneyIndexParser.fetch（mock client） ====================

def test_fetch_returns_parsed_data_when_html_ok():
    """fetch：client 返回渲染 HTML 时，返回解析后的 IndexData"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    html = _load_fixture('eastmoney_000300.html')
    fake_page = MagicMock()
    fake_page.content.return_value = html
    fake_client = MagicMock()
    fake_client.new_page.return_value.__enter__.return_value = fake_page
    parser = EastmoneyIndexParser(client=fake_client)
    data = parser.fetch('000300')
    assert data is not None
    assert data.index_code == '000300'
    assert data.close_price == 3416.88


def test_fetch_returns_none_when_html_none():
    """fetch：client 异常时返回 None"""
    from app.parser.eastmoney_index_parser import EastmoneyIndexParser
    fake_client = MagicMock()
    fake_client.new_page.side_effect = Exception('connect failed')
    parser = EastmoneyIndexParser(client=fake_client)
    assert parser.fetch('000300') is None
