#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创指数解析器
从腾讯财经获取实时行情数据
支持科创50(000688)和科创100(000698)
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
    pe_ratio: float
    pb_ratio: float
    update_time: str


class KcIndexParser:
    """科创指数解析器 - 支持科创50和科创100"""
    
    TENCENT_URL = "https://qt.gtimg.cn/q=sh{index_code}"
    
    INDEX_CONFIG = {
        '000688': {'name': '科创50'},
        '000698': {'name': '科创100'},
    }
    
    def __init__(self, index_code: str = '000688'):
        """
        初始化科创指数解析器

        Args:
            index_code: 指数代码，支持 '000688'(科创50) 或 '000698'(科创100)
        """
        if index_code not in self.INDEX_CONFIG:
            raise ValueError(f"不支持的指数代码: {index_code}，支持的代码: {list(self.INDEX_CONFIG.keys())}")
        
        self.index_code = index_code
        self.index_name = self.INDEX_CONFIG[index_code]['name']
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def fetch(self) -> Optional[KcIndexData]:
        """获取科创指数实时数据"""
        try:
            url = self.TENCENT_URL.format(index_code=self.index_code)
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
            
            if len(parts) >= 40:
                from ..utils.datetime_utils import get_beijing_now_str
                
                return KcIndexData(
                    index_code=self.index_code,
                    index_name=self.index_name,
                    open_price=float(parts[5]),
                    close_price=float(parts[3]),
                    high_price=float(parts[33]),
                    low_price=float(parts[34]),
                    change_percent=float(parts[32]),
                    volume=float(parts[6]),
                    amount=float(parts[37]) * 10000,
                    pe_ratio=float(parts[38]) if parts[38] else 0.0,
                    pb_ratio=float(parts[39]) if parts[39] else 0.0,
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


# 测试
if __name__ == '__main__':
    print("=" * 50)
    print("测试科创50解析器")
    print("=" * 50)
    
    parser_50 = KcIndexParser('000688')
    result_50 = parser_50.fetch()
    if result_50:
        print(f"指数代码: {result_50.index_code}")
        print(f"指数名称: {result_50.index_name}")
        print(f"开盘价: {result_50.open_price}")
        print(f"收盘价: {result_50.close_price}")
        print(f"最高价: {result_50.high_price}")
        print(f"最低价: {result_50.low_price}")
        print(f"涨跌幅: {result_50.change_percent}%")
        print(f"成交量: {result_50.volume}")
        print(f"成交额: {result_50.amount}")
        print(f"市盈率: {result_50.pe_ratio}")
        print(f"市净率: {result_50.pb_ratio}")
        print(f"更新时间: {result_50.update_time}")
    else:
        print("未获取到科创50数据")

    print("\n" + "=" * 50)
    print("测试科创100解析器")
    print("=" * 50)
    
    parser_100 = KcIndexParser('000698')
    result_100 = parser_100.fetch()
    if result_100:
        print(f"指数代码: {result_100.index_code}")
        print(f"指数名称: {result_100.index_name}")
        print(f"开盘价: {result_100.open_price}")
        print(f"收盘价: {result_100.close_price}")
        print(f"最高价: {result_100.high_price}")
        print(f"最低价: {result_100.low_price}")
        print(f"涨跌幅: {result_100.change_percent}%")
        print(f"成交量: {result_100.volume}")
        print(f"成交额: {result_100.amount}")
        print(f"市盈率: {result_100.pe_ratio}")
        print(f"市净率: {result_100.pb_ratio}")
        print(f"更新时间: {result_100.update_time}")
    else:
        print("未获取到科创100数据")
