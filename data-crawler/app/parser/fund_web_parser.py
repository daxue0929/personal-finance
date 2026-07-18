#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富 fundf10 网页解析器（Playwright 版）

与 fund_parser.py（requests 抓 .js 接口）并行，本解析器用 Playwright 抓 fundf10
网页 HTML，识别清洗基本概况字段。不动现有两个 parser。

设计（见 tasks/design-fund-web-scraper.md）：
- fetch(fund_code): 走 PlaywrightClient 取 HTML -> _parse
- _parse(html, fund_code): 纯函数，BeautifulSoup 解析，无外部依赖，可独立测试
- 依赖 app.utils.playwright_client 单例（browser 长连 + page 临时）

骨架阶段仅实现基本概况字段；持仓明细 / 阶段涨幅 / 费率信息留后续。
"""

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from ..utils.logger import logger
from ..utils.playwright_client import get_playwright_client


@dataclass
class FundWebData:
    """fundf10 基本概况解析结果（骨架阶段字段）"""
    fund_code: str
    fund_name: str
    fund_type: str
    establish_date: str
    fund_manager: str
    fund_size: float  # 净资产规模（亿元），无数据时为 0.0


class FundWebParser:
    """东方财富 fundf10 网页解析器"""

    FUND_F10_URL = "https://fundf10.eastmoney.com/jbgk_{code}.html"

    def __init__(self, client=None):
        """client 可注入便于测试；默认用 PlaywrightClient 单例。"""
        self._client = client if client is not None else get_playwright_client()

    def fetch(self, fund_code: str) -> Optional[FundWebData]:
        """抓取 fundf10 基本概况页并解析。

        Returns: FundWebData 或 None（取 HTML 失败 / 异常）
        """
        try:
            html = self._fetch_html(fund_code)
            if not html:
                return None
            return self._parse(html, fund_code)
        except Exception as e:
            logger.error(f"抓取基金 {fund_code} fundf10 数据异常: {e}")
            return None

    def _fetch_html(self, fund_code: str) -> Optional[str]:
        """通过 PlaywrightClient 取 fundf10 页面 HTML。"""
        url = self.FUND_F10_URL.format(code=fund_code)
        try:
            with self._client.new_page() as page:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                html = page.content()
            return html
        except Exception as e:
            logger.error(f"获取基金 {fund_code} fundf10 页面 HTML 失败: {e}")
            return None

    def _parse(self, html: str, fund_code: str) -> Optional[FundWebData]:
        """纯函数：解析 fundf10 基本概况 HTML。

        fundf10 基本概况页字段分布在两处：
        1. <table class="info w790"> 内的 <th>label</th><td>value</td>（部分 td 未闭合）
        2. <label>成立日期：<span>...</span></label> / <label>基金经理：<a>...</a></label>
        本实现两处都提取并合并，label 结构的干净值优先。
        """
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        th_fields = self._extract_th_fields(soup)
        label_fields = self._extract_label_fields(soup)

        fund_name = th_fields.get('基金简称') or th_fields.get('基金全称') or ''
        if not fund_name:
            logger.warning(f"基金 {fund_code} fundf10 未解析到基金名称")
            return None

        # 成立日期：label 结构的干净 ISO 日期优先，否则从 th 复合字段取
        establish_date = label_fields.get('成立日期') or self._extract_date_from_text(
            th_fields.get('成立日期/规模', ''))

        # 基金经理：th 的"基金经理人"或 label 的"基金经理"
        fund_manager = th_fields.get('基金经理人') or label_fields.get('基金经理') or ''

        # 基金规模：取"净资产规模"字段的亿元值（如 '53.82亿元（截止至：...）'）
        fund_size = self._parse_fund_size(th_fields.get('净资产规模', ''))

        return FundWebData(
            fund_code=fund_code,
            fund_name=fund_name,
            fund_type=th_fields.get('基金类型', ''),
            establish_date=establish_date,
            fund_manager=fund_manager,
            fund_size=fund_size,
        )

    @staticmethod
    def _extract_th_fields(soup: BeautifulSoup) -> dict:
        """从 <table class="info w790"> 的 th/td 配对提取字段。

        注意部分 td 未闭合（如基金代码 td 后直接接下一个 th），BeautifulSoup
        会将后续文本并入当前 td，因此仅取每对 th 后第一个 td 的直接文本。
        """
        fields = {}
        table = soup.find('table', class_='info')
        if not table:
            return fields
        for th in table.find_all('th'):
            label = th.get_text(strip=True).rstrip('：:')
            td = th.find_next_sibling('td')
            if td and label:
                value = td.get_text(strip=True)
                if label not in fields:
                    fields[label] = value
        return fields

    @staticmethod
    def _extract_label_fields(soup: BeautifulSoup) -> dict:
        """从 <label>label：<span>value</span></label> 结构提取字段。

        只取 label 的直接文本节点作为 key（不含子元素文本），
        值取首个 span/a 子元素文本。
        """
        fields = {}
        for label_tag in soup.find_all('label'):
            # 直接文本节点拼接（跳过子元素），得到干净的 "成立日期："
            direct_text = ''.join(
                s.strip() for s in label_tag.find_all(string=True, recursive=False)
            ).rstrip('：:')
            # 仅在 label 后代内找 span/a（find_next 会跨元素串值，曾误把"费率详情>"
            # 当作"购买手续费"的值）
            child = label_tag.find(['span', 'a'])
            value = child.get_text(strip=True) if child else ''
            if direct_text and value and direct_text not in fields:
                fields[direct_text] = value
        return fields

    @staticmethod
    def _parse_fund_size(text: str) -> float:
        """解析净资产规模文本，如 '53.82亿元（截止至：2026年03月31日）' -> 53.82。无数据返回 0.0。"""
        if not text:
            return 0.0
        # 优先匹配"亿元"前的数字
        m = re.search(r'(\d+(?:\.\d+)?)\s*亿元', text)
        if m:
            return float(m.group(1))
        # 兜底：取首个数字
        m = re.search(r'(\d+(?:\.\d+)?)', text)
        return float(m.group(1)) if m else 0.0

    @staticmethod
    def _extract_date_from_text(text: str) -> str:
        """从 '2021年03月04日 / 32.694亿份' 提取日期 '2021-03-04'。无则原样返回。"""
        if not text:
            return ''
        m = re.search(r'(\d{4})年(\d{2})月(\d{2})日', text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return text
