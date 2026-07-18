#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright 浏览器客户端管理模块

提供进程内复用的 browser 长连 + page 临时管理。参照 app/utils/db.py 的
DatabaseManager 单例模式：__new__ 单例 + 惰性 init + os.getenv 配置 + 模块级实例。

设计要点（见 tasks/design-fund-web-scraper.md）：
- browser 常驻（随进程生命周期），page 每次 new_page() 创建、with 退出关闭。
- 惰性 init：构造不连接，首次 new_page 才 _ensure_connected。
- 连接断开时 _ensure_connected 重新 connect_over_cdp。
- 异常捕获记录日志，不中断主流程（参照 run_with_trace_context 思想）。
- 浏览器二进制不在本镜像，通过 CDP 连接独立 browser 容器（PLAYWRIGHT_CDP_URL）。
"""

import os

from playwright.sync_api import sync_playwright

from .logger import logger


class PlaywrightClient:
    """Playwright 浏览器客户端单例

    browser 常驻复用，page 临时创建/关闭。通过 CDP 连接独立浏览器容器。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 单例 __init__ 每次都会执行，用守卫避免重复初始化
        if getattr(self, '_initialized', False):
            return
        self._playwright = None
        self._browser = None
        self._initialized = True

    def _ensure_connected(self):
        """惰性建立 / 重建 CDP 连接。连接有效则直接返回，失效则重连。"""
        if self._browser is not None and self._browser.is_connected():
            return

        cdp_url = os.getenv('PLAYWRIGHT_CDP_URL', '')
        if not cdp_url:
            raise RuntimeError('PLAYWRIGHT_CDP_URL 未配置，无法连接浏览器服务')

        # 旧连接已失效，先清理
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass

        logger.info(f"连接 Playwright 浏览器服务: {cdp_url}")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)
        logger.info("Playwright 浏览器服务已连接")

    def new_page(self):
        """获取一个新 page（上下文管理，用完自动关闭 page，browser 常驻）。

        连接失效时会自动重连一次。用法：
            with playwright_client.new_page() as page:
                page.goto(url)
                html = page.content()
        """
        self._ensure_connected()
        try:
            page = self._browser.new_page()
        except Exception as e:
            # 连接可能已失效，置空触发下次重连，并重试一次
            logger.warning(f"新建 page 失败，尝试重连: {e}")
            self._browser = None
            self._ensure_connected()
            page = self._browser.new_page()
        logger.debug("新建 Playwright page")
        return _PageContext(page)


class _PageContext:
    """page 上下文管理器：with 退出时关闭 page，browser 保持常驻。"""

    def __init__(self, page):
        self._page = page

    def __enter__(self):
        return self._page

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._page.close()
            logger.debug("Playwright page 已关闭")
        except Exception as e:
            logger.warning(f"关闭 Playwright page 异常: {e}")
        return False  # 不吞异常，交由调用方处理


# 模块级实例（进程内复用），参照 db.py 的 db_manager
playwright_client = PlaywrightClient()


def get_playwright_client():
    """获取 PlaywrightClient 单例（便捷访问器，参照 get_db_engine）"""
    return playwright_client
