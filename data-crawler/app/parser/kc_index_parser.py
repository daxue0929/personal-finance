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


class KcIndexParser:
    """指数解析器 - 支持科创50/100、沪深300、创业板50"""

    TENCENT_URL = "https://qt.gtimg.cn/q={market}{index_code}"

    INDEX_CONFIG = {
        '000688': {'name': '科创50', 'market': 'sh'},
        '000698': {'name': '科创100', 'market': 'sh'},
        '000300': {'name': '沪深300', 'market': 'sh'},
        '399673': {'name': '创业板50', 'market': 'sz'},
    }
    
    def __init__(self, index_code: str = '000688'):
        """
        初始化指数解析器

        Args:
            index_code: 指数代码，支持 '000688'(科创50)/'000698'(科创100)/
                        '000300'(沪深300)/'399673'(创业板50)
        """
        if index_code not in self.INDEX_CONFIG:
            raise ValueError(f"不支持的指数代码: {index_code}，支持的代码: {list(self.INDEX_CONFIG.keys())}")

        self.index_code = index_code
        self.index_name = self.INDEX_CONFIG[index_code]['name']
        self.market = self.INDEX_CONFIG[index_code]['market']
        
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
                    update_time=get_beijing_now_str('%Y-%m-%d %H:%M:%S')
                )
        except (ValueError, IndexError):
            pass
        return None

    @classmethod
    def get_supported_indices(cls) -> list:
        """获取支持的指数列表"""
        return [
            {'code': code, 'name': info['name']}
            for code, info in cls.INDEX_CONFIG.items()
        ]


if __name__ == '__main__':
    # 手动验证：遍历所有支持指数，打印抓取结果（含 sh/sz 前缀）
    for code, info in KcIndexParser.INDEX_CONFIG.items():
        print("=" * 50)
        print(f"测试 {info['name']}({code})  前缀: {info['market']}")
        print("=" * 50)
        result = KcIndexParser(code).fetch()
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
