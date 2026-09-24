#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支付宝基金交易记录解析器测试（TDD）

覆盖：
1. app/parser/alipay_record_parser.py - AlipayRecordParser 坐标聚类行、字段提取、异常行跳过
2. export_records_to_excel - 交易记录生成 Excel（复用 ExcelUtils）
3. ocr_image_to_excel - 完整管线（mock OCR 客户端）
4. 真实端到端集成测试（ocr_real marker，真实截图 → OCR → 解析 → 校验 4 条记录）

解析器单测手工构造 OcrTextBlock（模拟支付宝 1170x2532 截图布局），不依赖真实 OCR 引擎。

截图布局（每条记录）：
    [状态标签 已确认]              ← 右上，主行上方
    基金名称            -2169.49元  ← 主行：左侧名称 + 右侧金额
    卖出        2026-09-23 15:09:06 ← 明细行：左侧类型 + 右侧时间
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from conftest import requires_ocr

from app.utils.paddle_ocr_client import OcrTextBlock


def _block(text, x1, y1, x2, y2, confidence=0.99):
    """构造一个 OcrTextBlock（bbox 四点：左上/右上/右下/左下）"""
    return OcrTextBlock(
        text=text,
        confidence=confidence,
        bbox=[[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
    )


def _make_record_blocks(y_offset, fund_name, status, amount_text, trade_type, time_text):
    """按截图布局构造一条记录的 5 个文本块，返回 (blocks, expected_dict)"""
    blocks = [
        _block(status, 1010, y_offset - 60, 1130, y_offset - 25),      # 状态标签（右上，主行上方）
        _block(fund_name, 40, y_offset, 640, y_offset + 45),           # 基金名称（主行左）
        _block(amount_text, 880, y_offset, 1130, y_offset + 45),       # 金额（主行右）
        _block(trade_type, 40, y_offset + 75, 130, y_offset + 115),    # 交易类型（明细行左）
        _block(time_text, 780, y_offset + 75, 1130, y_offset + 115),   # 交易时间（明细行右）
    ]
    expected = {
        'fund_name': fund_name,
        'status': status,
        'trade_type': trade_type,
        'trade_time': time_text,
    }
    return blocks, expected


def _page_chrome_blocks():
    """页面非记录元素：标题栏 + 筛选器"""
    return [
        _block('交易记录', 500, 120, 670, 165),
        _block('全部', 950, 220, 1050, 255),
    ]


# 记录1：卖出 -2169.49元
RECORD1_Y = 430
RECORD1 = dict(
    fund_name='汇添富中证沪港深云计算产业ETF联接C', status='已确认',
    amount_text='-2169.49元', trade_type='卖出', time_text='2026-09-23 15:09:06',
    amount=-2169.49,
)
# 记录2：买入 1000.00元
RECORD2_Y = 680
RECORD2 = dict(
    fund_name='嘉实上证科创板芯片ETF发起联接C', status='已确认',
    amount_text='1000.00元', trade_type='买入', time_text='2026-09-19 01:31:54',
    amount=1000.00,
)


def _build_page_blocks():
    """构造完整页面：页面元素 + 两条记录"""
    blocks = _page_chrome_blocks()
    for rec, y in ((RECORD1, RECORD1_Y), (RECORD2, RECORD2_Y)):
        rec_blocks, _ = _make_record_blocks(
            y, rec['fund_name'], rec['status'], rec['amount_text'],
            rec['trade_type'], rec['time_text'],
        )
        blocks.extend(rec_blocks)
    return blocks


# ==================== 解析器单测 ====================

def test_parse_empty_returns_empty():
    """空输入返回空列表"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    assert AlipayRecordParser().parse([]) == []


def test_parse_single_sell_record():
    """单条卖出记录：各字段正确，金额为负"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks, _ = _make_record_blocks(
        RECORD1_Y, RECORD1['fund_name'], RECORD1['status'],
        RECORD1['amount_text'], RECORD1['trade_type'], RECORD1['time_text'],
    )
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 1
    r = records[0]
    assert r.fund_name == RECORD1['fund_name']
    assert r.trade_type == '卖出'
    assert r.amount == pytest.approx(-2169.49)
    assert r.status == '已确认'
    assert r.trade_time == '2026-09-23 15:09:06'


def test_parse_buy_record_positive_amount():
    """买入记录：金额为正"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks, _ = _make_record_blocks(
        RECORD2_Y, RECORD2['fund_name'], RECORD2['status'],
        RECORD2['amount_text'], RECORD2['trade_type'], RECORD2['time_text'],
    )
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 1
    assert records[0].trade_type == '买入'
    assert records[0].amount == pytest.approx(1000.00)


def test_parse_multiple_records_keep_order():
    """多条记录按页面顺序（自上而下）返回"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    records = AlipayRecordParser().parse(_build_page_blocks())

    assert len(records) == 2
    assert records[0].fund_name == RECORD1['fund_name']
    assert records[0].amount == pytest.approx(RECORD1['amount'])
    assert records[1].fund_name == RECORD2['fund_name']
    assert records[1].amount == pytest.approx(RECORD2['amount'])


def test_parse_unordered_blocks():
    """文本块顺序打乱仍按坐标正确解析"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = _build_page_blocks()
    shuffled = blocks[::-1]
    records = AlipayRecordParser().parse(shuffled)

    assert len(records) == 2
    assert records[0].fund_name == RECORD1['fund_name']
    assert records[1].fund_name == RECORD2['fund_name']


def test_page_chrome_rows_ignored():
    """标题/筛选器等非记录行不生成记录"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    records = AlipayRecordParser().parse(_page_chrome_blocks())
    assert records == []


def test_row_without_amount_not_a_record():
    """无金额的行（纯文本）不生成记录"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = [
        _block('这是一行普通文本', 40, 430, 640, 475),
        _block('卖出', 40, 505, 130, 545),
    ]
    assert AlipayRecordParser().parse(blocks) == []


def test_missing_detail_row_fallback_by_amount_sign():
    """缺明细行时：类型按金额符号推断（负=卖出），时间留空"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = [
        _block(RECORD1['fund_name'], 40, RECORD1_Y, 640, RECORD1_Y + 45),
        _block(RECORD1['amount_text'], 880, RECORD1_Y, 1130, RECORD1_Y + 45),
    ]
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 1
    assert records[0].trade_type == '卖出'
    assert records[0].trade_time == ''
    assert records[0].status == ''


def test_fund_name_split_into_multiple_blocks_joined():
    """基金名称被 OCR 拆成多个块时按 x 坐标拼接"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = [
        _block('汇添富中证沪港深', 40, RECORD1_Y, 300, RECORD1_Y + 45),
        _block('云计算产业ETF联接C', 310, RECORD1_Y, 640, RECORD1_Y + 45),
        _block(RECORD1['amount_text'], 880, RECORD1_Y, 1130, RECORD1_Y + 45),
        _block('卖出', 40, RECORD1_Y + 75, 130, RECORD1_Y + 115),
        _block(RECORD1['time_text'], 780, RECORD1_Y + 75, 1130, RECORD1_Y + 115),
    ]
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 1
    assert records[0].fund_name == '汇添富中证沪港深云计算产业ETF联接C'


# ==================== 基金详情页布局（单只基金交易记录页） ====================
# 布局：基金名称(代码) 在页面顶部仅一次；每条记录 = 主行(类型|金额) + 明细行(时间|状态)

FUND_LEVEL_HEADER = '华夏科创50ETF联接C(011613)'


def _make_fund_level_page(record_ys):
    """构造基金详情页交易记录：顶部基金名称 + 若干条定投记录"""
    blocks = [
        _block('交易记录', 500, 180, 670, 230),
        _block(FUND_LEVEL_HEADER, 280, 325, 640, 370),
    ]
    for y, time_text, status in record_ys:
        blocks.append(_block('定投', 40, y, 140, y + 45))                    # 类型（主行左）
        blocks.append(_block('300.00元', 880, y, 1040, y + 45))              # 金额（主行右）
        blocks.append(_block(time_text, 40, y + 65, 480, y + 105))           # 时间（明细行左）
        if status:
            blocks.append(_block(status, 830, y + 65, 1050, y + 105))        # 状态（明细行右）
    return blocks


def test_parse_fund_level_page():
    """基金详情页：类型在主行、基金名称取页面顶部、状态在明细行"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = _make_fund_level_page([
        (500, '2026-09-24 11:44:00', '交易进行中'),
        (730, '2026-09-23 11:38:10', ''),
    ])
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 2
    r = records[0]
    assert r.fund_name == FUND_LEVEL_HEADER
    assert r.trade_type == '定投'
    assert r.amount == pytest.approx(300.00)
    assert r.status == '交易进行中'
    assert r.trade_time == '2026-09-24 11:44:00'
    assert records[1].fund_name == FUND_LEVEL_HEADER
    assert records[1].status == ''


def test_time_without_space_normalized():
    """OCR 丢失日期与时间之间的空格时仍能提取并规范化"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = _make_fund_level_page([(500, '2026-09-2411:44:00', '')])
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 1
    assert records[0].trade_time == '2026-09-24 11:44:00'


def test_amount_split_blocks_fallback():
    """金额被拆成多个块（数字与"元"分离）时按全行拼接兜底识别"""
    from app.parser.alipay_record_parser import AlipayRecordParser
    blocks = _page_chrome_blocks()
    blocks.extend([
        _block(RECORD1['fund_name'], 40, RECORD1_Y, 640, RECORD1_Y + 45),
        _block('-2169.49', 880, RECORD1_Y, 1040, RECORD1_Y + 45),
        _block('元', 1050, RECORD1_Y, 1130, RECORD1_Y + 45),
        _block('卖出', 40, RECORD1_Y + 75, 130, RECORD1_Y + 115),
        _block(RECORD1['time_text'], 780, RECORD1_Y + 75, 1130, RECORD1_Y + 115),
    ])
    records = AlipayRecordParser().parse(blocks)

    assert len(records) == 1
    assert records[0].amount == pytest.approx(-2169.49)
    assert records[0].fund_name == RECORD1['fund_name']


# ==================== Excel 导出 ====================

def test_export_records_to_excel(tmp_path):
    """交易记录导出 Excel：表头与数据正确"""
    from app.parser.alipay_record_parser import (
        AlipayRecordParser, AlipayTradeRecord, export_records_to_excel,
    )
    from app.utils.excel_utils import ExcelUtils

    records = AlipayRecordParser().parse(_build_page_blocks())
    output = str(tmp_path / '交易记录.xlsx')
    export_records_to_excel(records, output)

    data = ExcelUtils.read_excel(output)
    assert len(data) == 2
    assert list(data[0].keys()) == ['基金名称', '交易类型', '金额', '状态', '交易时间']
    assert data[0]['基金名称'] == RECORD1['fund_name']
    assert data[0]['交易类型'] == '卖出'
    assert data[0]['金额'] == pytest.approx(-2169.49)
    assert data[0]['状态'] == '已确认'
    assert data[0]['交易时间'] == '2026-09-23 15:09:06'
    assert data[1]['交易类型'] == '买入'


def test_export_empty_records_writes_headers(tmp_path):
    """空记录导出：仅表头，不报错"""
    from app.parser.alipay_record_parser import export_records_to_excel
    from app.utils.excel_utils import ExcelUtils

    output = str(tmp_path / '空.xlsx')
    export_records_to_excel([], output)
    assert ExcelUtils.read_excel(output) == []


# ==================== 完整管线（mock OCR 客户端） ====================

def test_ocr_image_to_excel_pipeline(tmp_path):
    """完整管线：图片 → OCR → 解析 → Excel，返回解析记录"""
    from app.parser import alipay_record_parser as mod

    fake_client = MagicMock()
    fake_client.recognize.return_value = _build_page_blocks()
    output = str(tmp_path / '管线.xlsx')

    with patch.object(mod, 'get_paddle_ocr_client', return_value=fake_client):
        records = mod.ocr_image_to_excel('/tmp/fake.jpg', output)

    fake_client.recognize.assert_called_once_with('/tmp/fake.jpg')
    assert len(records) == 2
    assert records[0].fund_name == RECORD1['fund_name']

    from app.utils.excel_utils import ExcelUtils
    data = ExcelUtils.read_excel(output)
    assert len(data) == 2
    assert data[1]['基金名称'] == RECORD2['fund_name']


# ==================== 真实端到端集成测试 ====================

TEST_IMAGE = os.path.join(os.path.dirname(__file__), 'images', '20260924130253_9_374.jpg')

# 截图实际内容：华夏科创50ETF联接C(011613) 的 9 条定投记录（300.00元/条，自上而下）
EXPECTED_REAL_TIMES = [
    '2026-09-24 11:44:00', '2026-09-23 11:38:10', '2026-09-22 11:39:12',
    '2026-09-21 11:53:06', '2026-09-18 11:42:34', '2026-09-17 11:48:21',
    '2026-09-16 11:44:41', '2026-09-15 11:47:17', '2026-09-14 11:58:19',
]


@pytest.mark.ocr_real
@requires_ocr
def test_real_image_end_to_end(tmp_path):
    """真实截图端到端：OCR → 解析出 9 条定投记录 → Excel 落盘可读"""
    if not os.path.exists(TEST_IMAGE):
        pytest.skip(f'测试图片不存在: {TEST_IMAGE}')
    from app.parser.alipay_record_parser import ocr_image_to_excel
    from app.utils.excel_utils import ExcelUtils

    output = str(tmp_path / '真实交易记录.xlsx')
    records = ocr_image_to_excel(TEST_IMAGE, output)

    assert len(records) == 9
    for record, expected_time in zip(records, EXPECTED_REAL_TIMES):
        assert '华夏科创50' in record.fund_name
        assert '011613' in record.fund_name
        assert record.trade_type == '定投'
        assert record.amount == pytest.approx(300.00, abs=0.01)
        assert record.trade_time == expected_time
    # 首条记录状态为交易进行中（其余已完成记录页面不显示状态）
    assert records[0].status == '交易进行中'

    # Excel 落盘可读且行数一致
    data = ExcelUtils.read_excel(output)
    assert len(data) == 9
