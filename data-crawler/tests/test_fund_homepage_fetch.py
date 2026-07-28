#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金主页真实联网抓取 smoke 测试

与 test_fund_web_parser.py（mock 边界、不触网）互补：本文件**真实联网**，
用 PlaywrightClient 直接抓取 fund.eastmoney.com/001045.html 基金主页，
验证 Playwright 能把页面 HTML 正确拉下来。

注意：
- 主页结构与 fundf10 基本概况页不同，现有 FundWebParser._parse 解析不了主页，
  故本测试只验“HTML 拉取是否正确”（加载成功 / 非空 / title 身份命中），
  不走 _parse 出 FundWebData。
- 实测主页 JS 较重，wait_until='domcontentloaded'/'load' 会触发 renderer 崩溃
  （Page crashed），故用 wait_until='commit'：只等导航提交、不等 JS 渲染，
  取服务端返回的 HTML（含 <title>）。完整渲染抓取需先解决容器渲染崩溃问题。
- 依赖 browser 容器：需配置 PLAYWRIGHT_CDP_URL（本地 http://127.0.0.1:9222）。
  未配置时 skip，避免无 browser 环境误报失败。
- 触网，不在 CI 常规跑。
- 探查自主页 <title>：001045 = 华夏可转债增强债券A。
"""
import os
import re

import pytest


HOMEPAGE_URL = 'https://fund.eastmoney.com/001045.html'
FUND_CODE = '001045'
FUND_NAME = '华夏可转债增强债券A'  # 探查自主页 <title>


def _reset_singleton():
    """重置 PlaywrightClient 单例，避免与其它测试用例互相污染"""
    from app.utils import playwright_client as mod
    mod.PlaywrightClient._instance = None


@pytest.fixture(scope='module')
def homepage_html():
    """真实抓取主页 HTML 一次，模块内复用；未配置 CDP 则 skip。"""
    if not os.getenv('PLAYWRIGHT_CDP_URL'):
        pytest.skip('PLAYWRIGHT_CDP_URL 未配置，跳过真实联网抓取测试')
    _reset_singleton()
    from app.utils.playwright_client import PlaywrightClient
    client = PlaywrightClient()
    with client.new_page() as page:
        # commit：只等导航提交，避开主页 JS 渲染导致的 renderer 崩溃
        page.goto(HOMEPAGE_URL, wait_until='commit', timeout=30000)
        html = page.content()
    assert html, '主页 HTML 为空'
    return html


# ==================== HTML 拉取正确性 ====================

def test_homepage_html_non_empty(homepage_html):
    """主页被加载并取到非空 HTML（commit 阶段的服务端 HTML）"""
    assert len(homepage_html) > 500


def test_homepage_title_contains_fund_identity(homepage_html):
    """主页 <title> 含基金代码与名称（服务端渲染，拉取正确的标志）"""
    m = re.search(r'<title>(.*?)</title>', homepage_html, re.S)
    assert m, '未找到 <title>'
    title = m.group(1)
    assert FUND_CODE in title
    assert FUND_NAME in title
