#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创100指数解析器
从新浪财经获取实时行情数据
"""

import re
import requests
from dataclasses import dataclass
from typing import Optional

from ..utils.datetime_utils import get_beijing_now_str


@dataclass
class Kc100IndexData:
    index_code: str
    index_name: str
    current_price: float
    change: float
    change_pct: float
    volume: float
    amount: float
    update_time: str


class Kc100IndexParser:
    SINA_URL = "https://hq.sinajs.cn/list=s_sh000698"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        })

    def fetch(self) -> Optional[Kc100IndexData]:
        try:
            response = self.session.get(self.SINA_URL, timeout=10)
            if response.status_code == 200:
                return self._parse(response.text)
        except requests.RequestException:
            pass
        return None

    def _parse(self, content: str) -> Optional[Kc100IndexData]:
        try:
            match = re.search(r'"([^"]*)"', content)
            if match:
                data_str = match.group(1)
                parts = data_str.split(',')
                if len(parts) >= 5:
                    return Kc100IndexData(
                        index_code='000698',
                        index_name=parts[0],
                        current_price=float(parts[1]),
                        change=float(parts[2]),
                        change_pct=float(parts[3]),
                        volume=float(parts[4]),
                        amount=float(parts[5]) if len(parts) > 5 else 0,
                        update_time=get_beijing_now_str('%Y-%m-%d %H:%M:%S')
                    )
        except (ValueError, IndexError):
            pass
        return None
