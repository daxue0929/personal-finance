#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数解析器（腾讯财经实时行情）
支持科创50(000688)、科创100(000698)、沪深300(000300)、创业板50(399673)
sh 前缀用于上证指数，sz 前缀用于深证指数（创业板50）
"""

import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class KcIndexData:
    index_code: str
    index_name: str
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    change_percent: float
    volume: float
    amount: float
    turnover_rate: float
    pe_ratio: float
    pb_ratio: float
    update_time: str
    trade_date: Optional[str] = None  # 交易日（腾讯响应 parts[30] 前 8 位，YYYY-MM-DD）


class KcIndexParser:
    """指数解析器 - market 由调用方传入，不再硬编码 INDEX_CONFIG"""

    TENCENT_URL = "https://qt.gtimg.cn/q={market}{index_code}"
    SUPPORTED_MARKETS = ('sh', 'sz')
    # 已知指数代码 → 中文名。腾讯接口不返回名称，做兜底映射（storage 也有一道 DB 历史兜底，互为 backup）
    INDEX_NAME_MAP = {
        '000688': '科创50',
        '000698': '科创100',
        '000300': '沪深300',
        '399673': '创业板50',
    }

    def __init__(self, index_code: str, market: str):
        """
        初始化指数解析器

        Args:
            index_code: 指数代码，任意 6 位字符串（由调用方保证）
            market: 市场前缀，'sh'（沪）或 'sz'（深）
        """
        if market not in self.SUPPORTED_MARKETS:
            raise ValueError(f"market 必须是 sh/sz, got {market!r}")

        self.index_code = index_code
        # 兜底：已知 code 从 INDEX_NAME_MAP 取；未知 code 返回空，由 storage 再查 DB 历史
        self.index_name = self.INDEX_NAME_MAP.get(index_code, '')
        self.market = market

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def fetch(self) -> Optional[KcIndexData]:
        """获取科创指数实时数据"""
        try:
            url = self.TENCENT_URL.format(market=self.market, index_code=self.index_code)
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return self._parse(response.text)
        except requests.RequestException:
            pass
        return None

    def _parse(self, content: str) -> Optional[KcIndexData]:
        """解析腾讯财经接口返回的数据"""
        try:
            if '=' not in content:
                return None
                
            match = content.split('=')[1].strip('"')
            parts = match.split('~')
            
            if len(parts) >= 50:
                from ..utils.datetime_utils import get_beijing_now_str

                # 交易日：parts[30] 形如 "20260724161408"，取前 8 位 -> YYYY-MM-DD
                raw = parts[30] if len(parts) > 30 else ''
                trade_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) >= 8 else None

                return KcIndexData(
                    index_code=self.index_code,
                    index_name=self.index_name,
                    open_price=float(parts[5]),
                    close_price=float(parts[3]),
                    high_price=float(parts[33]),
                    low_price=float(parts[34]),
                    change_percent=float(parts[32]),
                    volume=float(parts[6]) / 10000,
                    amount=float(parts[37]) / 10000,
                    turnover_rate=float(parts[38]) if (len(parts) > 38 and parts[38]) else 0.0,
                    pe_ratio=float(parts[39]) if (len(parts) > 39 and parts[39]) else 0.0,
                    pb_ratio=float(parts[46]) if (len(parts) > 46 and parts[46]) else 0.0,
                    update_time=get_beijing_now_str('%Y-%m-%d %H:%M:%S'),
                    trade_date=trade_date
                )
        except (ValueError, IndexError):
            pass
        return None


if __name__ == '__main__':
    # 手动验证：遍历所有支持指数，打印抓取结果（含 sh/sz 前缀）
    samples = [('000688', 'sh'), ('000698', 'sh'), ('000300', 'sh'), ('399673', 'sz')]
    for code, market in samples:
        print("=" * 50)
        print(f"测试 指数 {code}  前缀: {market}")
        print("=" * 50)
        result = KcIndexParser(code, market).fetch()
        if result:
            print(f"  收盘价: {result.close_price}")
            print(f"  涨跌幅: {result.change_percent:+.2f}%")
            print(f"  成交量: {result.volume}")
            print(f"  成交额: {result.amount}")
            print(f"  PE(TTM): {result.pe_ratio}")
            print(f"  PB: {result.pb_ratio}")
            print(f"  更新时间: {result.update_time}")
        else:
            print("  未获取到数据")
        print()
