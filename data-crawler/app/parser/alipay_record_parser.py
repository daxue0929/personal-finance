#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支付宝基金交易记录解析器

将 PaddleOcrClient 识别出的文本块（带坐标）解析为结构化交易记录，
并支持导出 Excel。支持蚂蚁财富 App 两种「交易记录」页面：

1. 账户级交易记录列表（每条记录自带基金名称）：
       [状态标签 已确认]              ← 右上，主行上方
       基金名称            -2169.49元  ← 主行：左侧名称 + 右侧金额（卖出为负）
       卖出        2026-09-23 15:09:06 ← 明细行：左侧类型 + 右侧时间

2. 单只基金交易记录页（基金名称在页面顶部仅出现一次）：
       华夏科创50ETF联接C(011613)     ← 页面顶部
       定投                 300.00元   ← 主行：左侧类型 + 右侧金额
       2026-09-24 11:44:00      交易进行中 ← 明细行：左侧时间 + 右侧状态

解析思路：
1. 按 center_y 聚类成行（阈值取文本块中位高度的 0.8 倍）
2. 含金额（数字+元）的行为主行：金额左侧文本拼接为基金名称；
   主行无名称文本时（基金详情页），取页面顶部含基金代码 (xxxxxx) 的标题
3. 主行的下一行为明细行：提取交易类型与交易时间（OCR 可能丢失日期时间间的空格）
4. 状态在主行及其相邻行中搜索
"""

import re
from dataclasses import dataclass
from typing import List

from ..utils import ExcelUtils, get_paddle_ocr_client, logger
from ..utils.paddle_ocr_client import OcrTextBlock

# 交易类型关键词
TRADE_TYPE_WORDS = ('买入', '卖出', '分红', '定投', '转换')
# 状态关键词
STATUS_WORDS = ('已确认', '待确认', '确认中', '处理中', '交易进行中', '已撤销', '交易成功', '交易失败')
# 金额模式："-2169.49元" / "1000.00元"（允许千分位）
AMOUNT_RE = re.compile(r'([+-]?[\d,]+(?:\.\d+)?)\s*元')
# 时间模式：日期与时间之间的空格可能被 OCR 丢失（"2026-09-2411:44:00"），秒可选
TIME_RE = re.compile(r'(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}(?::\d{2})?)')
# 基金代码模式："华夏科创50ETF联接C(011613)"（兼容全角括号）
FUND_CODE_RE = re.compile(r'[(（]\d{6}[)）]')
# 纯数字块（金额被 OCR 拆块时的数字部分，基金名称拼接需排除）
PURE_NUMBER_RE = re.compile(r'^[+-]?[\d,]+(?:\.\d+)?$')
# Excel 表头
EXCEL_HEADERS = ['基金名称', '交易类型', '金额', '状态', '交易时间']


@dataclass
class AlipayTradeRecord:
    """支付宝基金交易记录（列表页可获取的字段）"""
    fund_name: str       # 基金名称
    trade_type: str      # 买入 / 卖出 / 定投 等
    amount: float        # 金额（元），买入为正、卖出为负（以截图符号为准）
    status: str          # 已确认 / 交易进行中 等
    trade_time: str      # 交易时间 "YYYY-MM-DD HH:MM:SS"（已规范化空格）


class AlipayRecordParser:
    """支付宝「交易记录」页面 OCR 文本块解析器"""

    def parse(self, blocks: List[OcrTextBlock]) -> List[AlipayTradeRecord]:
        """解析 OCR 文本块为交易记录列表（按页面自上而下顺序）"""
        rows = self._cluster_rows(blocks)
        page_fund_name = self._extract_page_fund_name(blocks)
        records = []
        for idx, row in enumerate(rows):
            amount_block, amount = self._find_amount(row)
            if amount_block is None:
                continue  # 非主行（标题/明细行/状态行）
            fund_name = self._extract_fund_name(row, amount_block) or page_fund_name
            if not fund_name:
                continue
            detail_row = rows[idx + 1] if idx + 1 < len(rows) else []
            records.append(AlipayTradeRecord(
                fund_name=fund_name,
                trade_type=self._extract_trade_type(row, detail_row, amount),
                amount=amount,
                status=self._extract_status(rows, idx),
                trade_time=self._extract_time(detail_row),
            ))
        return records

    @staticmethod
    def _cluster_rows(blocks: List[OcrTextBlock]) -> List[List[OcrTextBlock]]:
        """按 center_y 聚类成行，行内按 center_x 从左到右排序"""
        if not blocks:
            return []
        heights = sorted(b.height for b in blocks)
        median_height = heights[len(heights) // 2]
        threshold = max(15.0, median_height * 0.8)

        rows = []  # [{'cy': 行中心y, 'blocks': [...]}]
        for block in sorted(blocks, key=lambda b: b.center_y):
            if rows and abs(block.center_y - rows[-1]['cy']) <= threshold:
                rows[-1]['blocks'].append(block)
                n = len(rows[-1]['blocks'])
                rows[-1]['cy'] = (rows[-1]['cy'] * (n - 1) + block.center_y) / n
            else:
                rows.append({'cy': block.center_y, 'blocks': [block]})
        return [sorted(r['blocks'], key=lambda b: b.center_x) for r in rows]

    @staticmethod
    def _find_amount(row: List[OcrTextBlock]):
        """找行内金额块，返回 (block, 金额float)；无则 (None, None)。

        先逐块匹配，失败时全行文本拼接兜底（OCR 可能把数字与"元"拆成两块）。
        """
        for block in row:
            match = AMOUNT_RE.search(block.text)
            if match:
                return block, float(match.group(1).replace(',', ''))
        match = AMOUNT_RE.search(' '.join(b.text for b in row))
        if match:
            # 以最右侧块作为金额锚点（基金名称提取依赖与金额块的 x 坐标比较）
            return max(row, key=lambda b: b.center_x), float(match.group(1).replace(',', ''))
        return None, None

    @staticmethod
    def _extract_fund_name(row: List[OcrTextBlock], amount_block: OcrTextBlock) -> str:
        """基金名称：主行内金额块左侧的文本，按 x 顺序拼接。
        排除状态词/类型词/金额拆块（纯数字或"元"）。"""
        parts = [
            b.text for b in row
            if b is not amount_block
            and b.center_x < amount_block.center_x
            and not any(word in b.text for word in STATUS_WORDS)
            and not any(word in b.text for word in TRADE_TYPE_WORDS)
            and not PURE_NUMBER_RE.match(b.text.strip())
            and b.text.strip() != '元'
        ]
        return ''.join(parts).strip()

    @staticmethod
    def _extract_page_fund_name(blocks: List[OcrTextBlock]) -> str:
        """页面级基金名称：最上方含基金代码 (xxxxxx) 的文本块（基金详情页布局）"""
        for block in sorted(blocks, key=lambda b: b.center_y):
            if FUND_CODE_RE.search(block.text):
                return block.text.strip()
        return ''

    @staticmethod
    def _extract_trade_type(main_row: List[OcrTextBlock],
                            detail_row: List[OcrTextBlock], amount: float) -> str:
        """交易类型：先明细行（账户级布局），再主行（基金详情页布局），
        最后按金额符号兜底（负=卖出，正=买入）"""
        for row in (detail_row, main_row):
            for block in row:
                for word in TRADE_TYPE_WORDS:
                    if word in block.text:
                        return word
        return '卖出' if amount < 0 else '买入'

    @classmethod
    def _extract_status(cls, rows: List[List[OcrTextBlock]], row_idx: int) -> str:
        """状态：搜当前主行与明细行（下一行）；上一行仅当为"纯状态标签行"
        （无金额无时间，账户级布局的状态标签）时才搜，避免误取上一条记录
        明细行里的状态（基金详情页布局）"""
        for idx in (row_idx, row_idx + 1):
            if 0 <= idx < len(rows):
                found = cls._find_status_in_row(rows[idx])
                if found:
                    return found
        prev_idx = row_idx - 1
        if prev_idx >= 0:
            prev_row = rows[prev_idx]
            has_amount = any(AMOUNT_RE.search(b.text) for b in prev_row)
            has_time = any(TIME_RE.search(b.text) for b in prev_row)
            if not has_amount and not has_time:
                return cls._find_status_in_row(prev_row)
        return ''

    @staticmethod
    def _find_status_in_row(row: List[OcrTextBlock]) -> str:
        for block in row:
            for word in STATUS_WORDS:
                if word in block.text:
                    return word
        return ''

    @staticmethod
    def _extract_time(detail_row: List[OcrTextBlock]) -> str:
        """交易时间：明细行中匹配时间格式并规范化为 "YYYY-MM-DD HH:MM:SS"。
        先逐块找，再拼全行文本找（OCR 可能拆块或丢失日期时间间的空格）。"""
        for block in detail_row:
            match = TIME_RE.search(block.text)
            if match:
                return f'{match.group(1)} {match.group(2)}'
        match = TIME_RE.search(' '.join(b.text for b in detail_row))
        return f'{match.group(1)} {match.group(2)}' if match else ''


def export_records_to_excel(records: List[AlipayTradeRecord], file_path: str) -> None:
    """交易记录导出 Excel（复用 ExcelUtils，列：基金名称/交易类型/金额/状态/交易时间）"""
    data = [
        {
            '基金名称': r.fund_name,
            '交易类型': r.trade_type,
            '金额': r.amount,
            '状态': r.status,
            '交易时间': r.trade_time,
        }
        for r in records
    ]
    ExcelUtils.write_excel(file_path, data, sheet_name='交易记录', headers=EXCEL_HEADERS)


def ocr_image_to_excel(image_path: str, output_path: str) -> List[AlipayTradeRecord]:
    """一键管线：图片 → OCR 识别 → 解析交易记录 → 导出 Excel，返回解析记录"""
    blocks = get_paddle_ocr_client().recognize(image_path)
    records = AlipayRecordParser().parse(blocks)
    export_records_to_excel(records, output_path)
    logger.info(f'支付宝交易记录识别完成: {image_path} → {output_path}, 共 {len(records)} 条')
    return records
