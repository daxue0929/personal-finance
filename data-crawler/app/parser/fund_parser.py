import requests
import json
from typing import Optional, Dict, Any

from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_timestamp, timestamp_ms_to_date_str


class FundParser:
    BASE_URL = "https://fund.eastmoney.com/pingzhongdata"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def fetch_fund_data(self, fund_code: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/{fund_code}.js?v={get_beijing_timestamp()}"

        try:
            response = self.session.get(url, timeout=10)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                return self._parse_js_content(response.text, fund_code)

            logger.warning(f"获取基金 {fund_code} 数据失败，状态码: {response.status_code}")
            return None

        except requests.RequestException as e:
            logger.error(f"获取基金 {fund_code} 数据异常: {e}")
            return None

    def fetch_multiple_funds(self, fund_codes: list) -> Dict[str, Dict[str, Any]]:
        results = {}
        for code in fund_codes:
            logger.info(f"正在获取基金 {code} 的数据...")
            data = self.fetch_fund_data(code)
            if data:
                results[code] = data
        return results

    def _parse_js_content(self, content: str, fund_code: str) -> Optional[Dict[str, Any]]:
        data = {'fund_code': fund_code}

        name = self._extract_value(content, 'fS_name = "', '";')
        if name:
            data['fund_name'] = name

        nav_data = self._extract_net_worth_trend(content)
        if nav_data:
            data.update(nav_data)

        data['fund_type'] = self._extract_value(content, 'fundType = "', '";') or '未知'
        data['fund_manager'] = self._extract_value(content, 'fundManager = "', '";') or ''
        data['establish_date'] = self._extract_value(content, 'establishDate = "', '";') or None

        return data if data.get('fund_name') else None

    def _extract_value(self, content: str, start_marker: str, end_marker: str) -> Optional[str]:
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return None
        start_idx += len(start_marker)
        end_idx = content.find(end_marker, start_idx)
        if end_idx == -1:
            return None
        return content[start_idx:end_idx]

    def _extract_net_worth_trend(self, content: str) -> Optional[Dict[str, Any]]:
        start_marker = 'netWorthTrend = '
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return None

        start_idx += len(start_marker)
        end_idx = content.find('];', start_idx)
        if end_idx == -1:
            return None

        nav_data_str = content[start_idx:end_idx + 1]
        try:
            nav_list = json.loads(nav_data_str)
            if nav_list:
                latest = nav_list[-1]
                return {
                    'net_asset_value': str(latest.get('y', 0)),
                    'net_value_date': timestamp_ms_to_date_str(latest.get('x', 0))
                }
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.warning(f"解析净值数据失败: {e}")

        return None
