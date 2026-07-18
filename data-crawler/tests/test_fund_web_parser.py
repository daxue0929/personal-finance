#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright 网页抓取解析器测试（TDD）

覆盖：
1. app/utils/playwright_client.py - PlaywrightClient 单例、惰性 init、page 临时关闭、连接断开重连、CDP 未配置报错
2. app/parser/fund_web_parser.py - FundWebParser._parse 纯函数（喂真实 HTML fixture）、fetch（mock client）

测试一律 mock 边界（playwright 驱动 / PlaywrightClient），不连真实浏览器、不触网。
真实 HTML fixture 由浏览器服务抓取后落盘到 tests/fixtures/fundf10_basic.html。
"""
import os
from unittest.mock import MagicMock, patch

import pytest


# ==================== PlaywrightClient 单例与生命周期 ====================

def _reset_singleton():
    """重置 PlaywrightClient 单例，避免用例间互相污染"""
    from app.utils import playwright_client as mod
    mod.PlaywrightClient._instance = None


@pytest.fixture(autouse=True)
def reset_client():
    """每个用例前重置单例与 CDP 环境变量"""
    _reset_singleton()
    old = os.environ.pop('PLAYWRIGHT_CDP_URL', None)
    yield
    if old is not None:
        os.environ['PLAYWRIGHT_CDP_URL'] = old
    _reset_singleton()


def test_client_is_singleton():
    """__new__ 返回同一实例"""
    from app.utils.playwright_client import PlaywrightClient
    with patch.object(PlaywrightClient, '_ensure_connected', return_value=None):
        a = PlaywrightClient()
        b = PlaywrightClient()
    assert a is b


def test_client_lazy_init_no_connect_on_construct():
    """构造时不立即连接（惰性 init：首次 new_page 才连）"""
    from app.utils.playwright_client import PlaywrightClient
    with patch.object(PlaywrightClient, '_ensure_connected') as m:
        PlaywrightClient()
        m.assert_not_called()


def test_cdp_url_not_configured_raises():
    """PLAYWRIGHT_CDP_URL 未配置时 new_page 抛 RuntimeError"""
    from app.utils.playwright_client import PlaywrightClient
    client = PlaywrightClient()
    with pytest.raises(RuntimeError, match='CDP'):
        client.new_page()


def test_new_page_closes_page_after_context_exit():
    """page 临时：with 退出后 page 被关闭，browser 常驻不关"""
    from app.utils.playwright_client import PlaywrightClient
    os.environ['PLAYWRIGHT_CDP_URL'] = 'http://browser:9222'

    fake_page = MagicMock()
    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page

    with patch.object(PlaywrightClient, '_ensure_connected') as m_connect:
        client = PlaywrightClient()
        client._browser = fake_browser
        with client.new_page() as page:
            assert page is fake_page
        fake_page.close.assert_called_once()
        # browser 常驻，未被关闭
        fake_browser.close.assert_not_called()


def test_ensure_connected_connects_when_no_browser():
    """首次连接：_browser 为 None 时 connect_over_cdp"""
    from app.utils.playwright_client import PlaywrightClient
    os.environ['PLAYWRIGHT_CDP_URL'] = 'http://browser:9222'

    fake_browser = MagicMock()
    fake_browser.is_connected.return_value = True
    fake_pw = MagicMock()
    fake_pw.start.return_value = fake_pw  # sync_playwright().start() 返回自身
    fake_pw.chromium.connect_over_cdp.return_value = fake_browser

    with patch('app.utils.playwright_client.sync_playwright',
               return_value=fake_pw):
        client = PlaywrightClient()
        client._ensure_connected()
        assert client._browser is fake_browser
        fake_pw.chromium.connect_over_cdp.assert_called_once_with('http://browser:9222')


def test_ensure_connected_reconnects_when_browser_lost():
    """已连接但 browser.is_connected() 返回 False 时重新 connect_over_cdp"""
    from app.utils.playwright_client import PlaywrightClient
    os.environ['PLAYWRIGHT_CDP_URL'] = 'http://browser:9222'

    fake_browser = MagicMock()
    fake_browser.is_connected.return_value = False  # 连接已失效
    fake_pw = MagicMock()
    fake_pw.start.return_value = fake_pw
    fake_pw.chromium.connect_over_cdp.return_value = fake_browser

    with patch('app.utils.playwright_client.sync_playwright',
               return_value=fake_pw):
        client = PlaywrightClient()
        client._browser = fake_browser  # 模拟已连接过
        client._playwright = fake_pw
        client._ensure_connected()
        # 失效后应重新调用 connect_over_cdp
        assert fake_pw.chromium.connect_over_cdp.call_count == 1


def test_new_page_reconnects_on_failure():
    """new_page 失败时置空 browser 并重连一次"""
    from app.utils.playwright_client import PlaywrightClient
    os.environ['PLAYWRIGHT_CDP_URL'] = 'http://browser:9222'

    fake_browser = MagicMock()
    fake_browser.is_connected.return_value = True
    fake_browser.new_page.side_effect = [Exception('disconnected'), MagicMock()]
    fake_pw = MagicMock()
    fake_pw.start.return_value = fake_pw
    fake_pw.chromium.connect_over_cdp.return_value = fake_browser

    with patch('app.utils.playwright_client.sync_playwright',
               return_value=fake_pw):
        client = PlaywrightClient()
        client._browser = fake_browser
        client._playwright = fake_pw
        with client.new_page() as page:
            pass
        # 首次 new_page 失败 -> 重连(connect_over_cdp 再调一次) -> 第二次 new_page 成功
        assert fake_pw.chromium.connect_over_cdp.call_count == 1
        assert fake_browser.new_page.call_count == 2


def test_new_page_exception_does_not_break_client():
    """new_page 异常时捕获记录，不影响后续调用（不中断主流程）"""
    from app.utils.playwright_client import PlaywrightClient
    os.environ['PLAYWRIGHT_CDP_URL'] = 'http://browser:9222'

    fake_browser = MagicMock()
    fake_browser.new_page.side_effect = Exception('boom')

    with patch.object(PlaywrightClient, '_ensure_connected'):
        client = PlaywrightClient()
        client._browser = fake_browser
        with pytest.raises(Exception):
            with client.new_page():
                pass


# ==================== FundWebParser._parse 纯函数 ====================

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'fundf10_basic.html')


def _load_fixture():
    with open(FIXTURE_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def test_parse_basic_fields_from_real_html():
    """_parse 喂真实 fundf10 HTML，解析出基本概况字段"""
    pytest.importorskip('bs4')
    from app.parser.fund_web_parser import FundWebParser, FundWebData
    html = _load_fixture()
    data = FundWebParser()._parse(html, '011613')
    assert isinstance(data, FundWebData)
    assert data.fund_code == '011613'
    assert data.fund_name  # 非空
    assert data.fund_type
    assert data.fund_manager


def test_parse_empty_html_returns_none():
    """空 HTML 返回 None"""
    from app.parser.fund_web_parser import FundWebParser
    assert FundWebParser()._parse('', '011613') is None


def test_parse_missing_fields_returns_none_or_partial():
    """HTML 缺关键字段（基金名）时返回 None"""
    from app.parser.fund_web_parser import FundWebParser
    html = '<html><body>无关内容</body></html>'
    assert FundWebParser()._parse(html, '011613') is None


# ==================== FundWebParser.fetch（mock client） ====================

def test_fetch_returns_parsed_data_when_html_ok():
    """fetch：client 返回 HTML 时，返回解析后的 FundWebData"""
    from app.parser.fund_web_parser import FundWebParser
    html = _load_fixture()
    fake_client = MagicMock()
    fake_client.new_page.return_value.__enter__.return_value = MagicMock(
        goto=MagicMock(),
        content=MagicMock(return_value=html)
    )
    parser = FundWebParser(client=fake_client)
    data = parser.fetch('011613')
    assert data is not None
    assert data.fund_code == '011613'


def test_fetch_returns_none_when_html_none():
    """fetch：client 取不到 HTML 时返回 None"""
    from app.parser.fund_web_parser import FundWebParser
    fake_client = MagicMock()
    fake_client.new_page.return_value.__enter__.return_value = MagicMock(
        goto=MagicMock(),
        content=MagicMock(return_value=None)
    )
    parser = FundWebParser(client=fake_client)
    assert parser.fetch('011613') is None


def test_fetch_returns_none_on_client_exception():
    """fetch：client 异常时返回 None，不抛"""
    from app.parser.fund_web_parser import FundWebParser
    fake_client = MagicMock()
    fake_client.new_page.side_effect = Exception('connect failed')
    parser = FundWebParser(client=fake_client)
    assert parser.fetch('011613') is None


# ==================== fetch_fund_detail_task（抓取+打印，不落库） ====================

def test_task_iterates_and_prints_structured_data(monkeypatch, caplog):
    """task 遍历 fund_codes，对每只基金打印结构化结果"""
    from app.task import fetch_fund_detail_task as task_mod
    from app.parser.fund_web_parser import FundWebData

    fake_parser = MagicMock()
    fake_parser.fetch.side_effect = [
        FundWebData('011613', '华夏科创50ETF联接C', '指数型-股票', '2021-03-04', '荣膺', 32.694),
        None,  # 第二只抓取失败
    ]
    monkeypatch.setattr(task_mod, 'FundWebParser', lambda: fake_parser)
    monkeypatch.setattr(task_mod, '_get_fund_codes', lambda: ['011613', '012349'])

    with caplog.at_level('INFO'):
        task_mod.fetch_fund_detail_task(force_run=True)

    # 两只都尝试了
    assert fake_parser.fetch.call_count == 2
    # 成功的打印了结构化字段
    joined = '\n'.join(r.message for r in caplog.records)
    assert '011613' in joined
    assert '华夏科创50ETF联接C' in joined


def test_task_single_failure_does_not_break_others(monkeypatch, caplog):
    """单只基金异常不中断整体遍历"""
    from app.task import fetch_fund_detail_task as task_mod
    from app.parser.fund_web_parser import FundWebData

    fake_parser = MagicMock()
    fake_parser.fetch.side_effect = [
        Exception('boom'),
        FundWebData('012349', '天弘恒生科技', '指数型', '2021-01-01', '经理B', 1.0),
    ]
    monkeypatch.setattr(task_mod, 'FundWebParser', lambda: fake_parser)
    monkeypatch.setattr(task_mod, '_get_fund_codes', lambda: ['011613', '012349'])

    with caplog.at_level('INFO'):
        task_mod.fetch_fund_detail_task(force_run=True)

    # 第二只仍被处理
    assert fake_parser.fetch.call_count == 2
    joined = '\n'.join(r.message for r in caplog.records)
    assert '012349' in joined


def test_task_no_fund_codes_skips(monkeypatch):
    """无基金代码时直接返回，不调 parser"""
    from app.task import fetch_fund_detail_task as task_mod

    fake_parser = MagicMock()
    monkeypatch.setattr(task_mod, 'FundWebParser', lambda: fake_parser)
    monkeypatch.setattr(task_mod, '_get_fund_codes', lambda: [])

    task_mod.fetch_fund_detail_task(force_run=True)
    fake_parser.fetch.assert_not_called()
