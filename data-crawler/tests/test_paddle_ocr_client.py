#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaddleOCR 客户端测试（TDD）

覆盖：
1. app/utils/paddle_ocr_client.py - PaddleOcrClient 单例、惰性初始化、结果标准化、异常处理
2. OcrTextBlock 数据模型几何属性
3. 真实 OCR 集成测试（ocr_real marker，用支付宝交易记录截图）

单测一律 mock paddleocr 模块（patch sys.modules），不触发真实模型加载。
真实集成测试需安装 requirements-ocr.txt，首次运行会下载模型（约几百 MB）。
"""
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from conftest import requires_ocr


def _reset_singleton():
    """重置 PaddleOcrClient 单例与模块级实例，避免用例间互相污染"""
    from app.utils import paddle_ocr_client as mod
    mod.PaddleOcrClient._instance = None
    mod.paddle_ocr_client = mod.PaddleOcrClient()


@pytest.fixture(autouse=True)
def reset_client():
    _reset_singleton()
    yield
    _reset_singleton()


def _make_fake_paddleocr_module(predict_return=None, predict_side_effect=None):
    """构造假的 paddleocr 模块，PaddleOCR 类返回 mock 引擎"""
    fake = ModuleType('paddleocr')
    engine = MagicMock()
    if predict_side_effect is not None:
        engine.predict.side_effect = predict_side_effect
    else:
        engine.predict.return_value = predict_return
    fake.PaddleOCR = MagicMock(return_value=engine)
    return fake, engine


def _fake_ocr_result(texts, scores, polys):
    """构造 paddleocr 3.x predict 的单条 OCRResult（dict-like）"""
    return {'rec_texts': texts, 'rec_scores': scores, 'rec_polys': polys}


# ==================== 单例与惰性初始化 ====================

def test_client_is_singleton():
    """__new__ 返回同一实例"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    a = PaddleOcrClient()
    b = PaddleOcrClient()
    assert a is b


def test_lazy_init_no_engine_on_construct():
    """构造时不创建 PaddleOCR 引擎（惰性初始化：首次 recognize 才加载模型）"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    fake, _ = _make_fake_paddleocr_module()
    with patch.dict(sys.modules, {'paddleocr': fake}):
        PaddleOcrClient()
        fake.PaddleOCR.assert_not_called()


def test_first_recognize_triggers_init():
    """首次 recognize 才创建 PaddleOCR 引擎实例"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    fake, _ = _make_fake_paddleocr_module(predict_return=[])
    with patch.dict(sys.modules, {'paddleocr': fake}):
        client = PaddleOcrClient()
        client.recognize('/tmp/fake.jpg')
        fake.PaddleOCR.assert_called_once()


def test_second_recognize_reuses_engine():
    """二次 recognize 复用同一引擎，不重复加载模型"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    fake, _ = _make_fake_paddleocr_module(predict_return=[])
    with patch.dict(sys.modules, {'paddleocr': fake}):
        client = PaddleOcrClient()
        client.recognize('/tmp/a.jpg')
        client.recognize('/tmp/b.jpg')
        fake.PaddleOCR.assert_called_once()


# ==================== 结果标准化 ====================

def test_recognize_returns_text_blocks():
    """predict 结果被标准化为 OcrTextBlock 列表（text/confidence/bbox）"""
    from app.utils.paddle_ocr_client import PaddleOcrClient, OcrTextBlock
    result = _fake_ocr_result(
        texts=['汇添富中证沪港深云计算产业ETF联接C', '-2169.49元'],
        scores=[0.998, 0.995],
        polys=[
            [[40, 430], [640, 430], [640, 475], [40, 475]],
            [[880, 430], [1130, 430], [1130, 475], [880, 475]],
        ],
    )
    fake, _ = _make_fake_paddleocr_module(predict_return=[result])
    with patch.dict(sys.modules, {'paddleocr': fake}):
        client = PaddleOcrClient()
        blocks = client.recognize('/tmp/fake.jpg')

    assert len(blocks) == 2
    assert all(isinstance(b, OcrTextBlock) for b in blocks)
    assert blocks[0].text == '汇添富中证沪港深云计算产业ETF联接C'
    assert blocks[0].confidence == pytest.approx(0.998)
    assert blocks[0].bbox == [[40, 430], [640, 430], [640, 475], [40, 475]]
    assert blocks[1].text == '-2169.49元'


def test_recognize_empty_result_returns_empty_list():
    """predict 返回空列表时安全返回 []"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    fake, _ = _make_fake_paddleocr_module(predict_return=[])
    with patch.dict(sys.modules, {'paddleocr': fake}):
        client = PaddleOcrClient()
        assert client.recognize('/tmp/fake.jpg') == []


def test_recognize_missing_keys_returns_empty_list():
    """OCRResult 缺 rec_texts 键时安全返回 []"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    fake, _ = _make_fake_paddleocr_module(predict_return=[{}])
    with patch.dict(sys.modules, {'paddleocr': fake}):
        client = PaddleOcrClient()
        assert client.recognize('/tmp/fake.jpg') == []


def test_recognize_paddle_exception_returns_empty_list():
    """OCR 引擎内部异常不中断调用方，返回空列表"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    fake, _ = _make_fake_paddleocr_module(predict_side_effect=RuntimeError('模型推理失败'))
    with patch.dict(sys.modules, {'paddleocr': fake}):
        client = PaddleOcrClient()
        assert client.recognize('/tmp/fake.jpg') == []


def test_paddleocr_not_installed_raises_friendly_error():
    """未安装 paddleocr 时抛带安装指引的 ImportError"""
    from app.utils.paddle_ocr_client import PaddleOcrClient
    client = PaddleOcrClient()
    with patch.dict(sys.modules, {'paddleocr': None}):
        with pytest.raises(ImportError, match='requirements-ocr'):
            client.recognize('/tmp/fake.jpg')


# ==================== OcrTextBlock 几何属性 ====================

def test_ocr_text_block_geometry_properties():
    """bbox 几何属性计算正确（center/top/bottom/left/right）"""
    from app.utils.paddle_ocr_client import OcrTextBlock
    block = OcrTextBlock(
        text='测试',
        confidence=0.99,
        bbox=[[100, 200], [300, 200], [300, 260], [100, 260]],
    )
    assert block.center_x == pytest.approx(200)
    assert block.center_y == pytest.approx(230)
    assert block.left == 100
    assert block.right == 300
    assert block.top == 200
    assert block.bottom == 260
    assert block.width == 200
    assert block.height == 60


# ==================== 真实 OCR 集成测试 ====================

TEST_IMAGE = os.path.join(os.path.dirname(__file__), 'images', '20260924130253_9_374.jpg')


@pytest.mark.ocr_real
@requires_ocr
def test_real_ocr_returns_text_blocks():
    """真实支付宝截图：返回非空文本块，字段格式合法"""
    if not os.path.exists(TEST_IMAGE):
        pytest.skip(f'测试图片不存在: {TEST_IMAGE}')
    from app.utils.paddle_ocr_client import PaddleOcrClient
    client = PaddleOcrClient()
    blocks = client.recognize(TEST_IMAGE)

    assert len(blocks) > 0
    assert all(b.text.strip() for b in blocks)
    assert all(0.0 <= b.confidence <= 1.0 for b in blocks)
    assert all(len(b.bbox) == 4 for b in blocks)


@pytest.mark.ocr_real
@requires_ocr
def test_real_ocr_detects_known_keywords():
    """真实截图（华夏科创50 定投记录页）：识别出预期关键词"""
    if not os.path.exists(TEST_IMAGE):
        pytest.skip(f'测试图片不存在: {TEST_IMAGE}')
    from app.utils.paddle_ocr_client import PaddleOcrClient
    client = PaddleOcrClient()
    blocks = client.recognize(TEST_IMAGE)
    all_text = ' '.join(b.text for b in blocks)

    assert '交易记录' in all_text
    assert '定投' in all_text
    assert '元' in all_text
