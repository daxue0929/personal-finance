#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创50指数解析器
从腾讯财经获取实时行情数据
指数代码: 000688
"""

import re
import requests
from dataclasses import dataclass
from typing import Optional

from ..utils.datetime_utils import get_beijing_now_str


@dataclass
class Kc50IndexData:
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
    pe_percentile: float
    pb_ratio: float
    update_time: str


class Kc50IndexParser:
    TENCENT_URL = "https://qt.gtimg.cn/q=sh{index_code}"
    EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.{index_code}&fields=f57,f58,f107,f108,f116,f117,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def fetch(self) -> Optional[Kc50IndexData]:
        # 尝试腾讯财经接口
        result = self._fetch_from_tencent()
        if result:
            return result
        
        # 如果腾讯接口失败，尝试东方财富网接口
        return self._fetch_from_eastmoney()

    def _fetch_from_tencent(self) -> Optional[Kc50IndexData]:
        try:
            url = self.TENCENT_URL.format(index_code='000688')
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return self._parse_tencent(response.text)
        except requests.RequestException as e:
            pass
        return None

    def _parse_tencent(self, content: str) -> Optional[Kc50IndexData]:
        try:
            # 腾讯接口返回格式: v_sh000688="1~科创50~000688~...
            if '=' not in content:
                return None
                
            match = content.split('=')[1].strip('"')
            parts = match.split('~')
            
            if len(parts) >= 40:
                return Kc50IndexData(
                    index_code='000688',
                    index_name=parts[1],
                    open_price=float(parts[5]),      # 开盘价
                    close_price=float(parts[3]),     # 当前价/收盘价
                    high_price=float(parts[33]),     # 最高价
                    low_price=float(parts[34]),      # 最低价
                    change_percent=float(parts[32]), # 涨跌幅(%)
                    volume=float(parts[6]),          # 成交量
                    amount=float(parts[37]) * 10000, # 成交额(万元) -> 元
                    pe_ratio=float(parts[38]),       # 市盈率
                    pe_percentile=0.0,
                    pb_ratio=float(parts[39]),       # 市净率
                    update_time=get_beijing_now_str('%Y-%m-%d %H:%M:%S')
                )
        except (ValueError, IndexError):
            pass
        return None

    def _fetch_from_eastmoney(self) -> Optional[Kc50IndexData]:
        try:
            url = self.EASTMONEY_URL.format(index_code='000688')
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return self._parse_eastmoney(response.json())
        except requests.RequestException as e:
            pass
        return None

    def _parse_eastmoney(self, data: dict) -> Optional[Kc50IndexData]:
        try:
            record = data.get('data', {})
            
            if not record:
                return None
                
            return Kc50IndexData(
                index_code='000688',
                index_name=record.get('f58', '科创50'),
                open_price=float(record.get('f62', 0)),
                close_price=float(record.get('f57', 0)),
                high_price=float(record.get('f59', 0)),
                low_price=float(record.get('f61', 0)),
                change_percent=float(record.get('f74', 0)),
                volume=float(record.get('f63', 0)),
                amount=float(record.get('f64', 0)),
                pe_ratio=float(record.get('f86', 0)),
                pe_percentile=0.0,
                pb_ratio=float(record.get('f87', 0)),
                update_time=get_beijing_now_str('%Y-%m-%d %H:%M:%S')
            )
        except (ValueError, IndexError):
            pass
        return None
