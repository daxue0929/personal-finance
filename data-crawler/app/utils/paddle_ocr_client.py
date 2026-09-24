#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaddleOCR 客户端模块

提供进程内复用的 OCR 引擎单例。参照 app/utils/playwright_client.py 的
PlaywrightClient 单例模式：__new__ 单例 + 惰性 init + 模块级实例。

设计要点：
- PaddleOCR 模型加载开销大（秒级 + 数百 MB 内存），进程内复用同一引擎实例。
- 惰性 init：构造不加载模型，首次 recognize 才 _ensure_initialized。
- paddleocr 延迟 import（在 _ensure_initialized 内部），未安装时 import 本
  模块不受影响（paddleocr import 有副作用，且 OCR 是可选本地能力）。
- 识别异常返回空列表并记 ERROR 日志，不中断调用方（参照 run_with_trace_context 思想）。
- OCR 依赖不进生产镜像，安装：pip install -r requirements-ocr.txt
"""

from dataclasses import dataclass
from typing import List

from .logger import logger


@dataclass
class OcrTextBlock:
    """OCR 识别出的单个文本块

    bbox 为四点坐标：左上、右上、右下、左下。
    几何属性供解析层做行聚类（center_y）与字段定位（center_x）。
    """
    text: str
    confidence: float
    bbox: List[List[float]]

    @property
    def center_x(self) -> float:
        return sum(p[0] for p in self.bbox) / len(self.bbox)

    @property
    def center_y(self) -> float:
        return sum(p[1] for p in self.bbox) / len(self.bbox)

    @property
    def left(self) -> float:
        return min(p[0] for p in self.bbox)

    @property
    def right(self) -> float:
        return max(p[0] for p in self.bbox)

    @property
    def top(self) -> float:
        return min(p[1] for p in self.bbox)

    @property
    def bottom(self) -> float:
        return max(p[1] for p in self.bbox)

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


class PaddleOcrClient:
    """PaddleOCR 引擎单例（惰性初始化，模型加载开销大）

    用法：
        from app.utils.paddle_ocr_client import get_paddle_ocr_client
        blocks = get_paddle_ocr_client().recognize('/path/to/image.jpg')
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 单例 __init__ 每次都会执行，用守卫避免重复初始化
        if getattr(self, '_initialized', False):
            return
        self._ocr = None  # PaddleOCR 引擎实例，惰性创建
        self._initialized = True

    def _ensure_initialized(self):
        """惰性加载 PaddleOCR 引擎（首次调用时加载模型，耗时数秒）"""
        if self._ocr is not None:
            return
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            raise ImportError(
                '未安装 paddleocr，请先安装：pip install -r requirements-ocr.txt'
            )
        logger.info('初始化 PaddleOCR 引擎（首次运行需下载模型，请稍候）...')
        # 关闭文档方向分类/曲面矫正/文本行方向分类，截图场景不需要，可提速
        self._ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang='ch',
        )
        logger.info('PaddleOCR 引擎初始化完成')

    def recognize(self, image_path: str) -> List[OcrTextBlock]:
        """识别图片文本，返回标准化文本块列表。

        Args:
            image_path: 图片文件路径

        Returns:
            OcrTextBlock 列表；识别失败/无结果时返回空列表
        """
        self._ensure_initialized()
        try:
            raw_results = self._ocr.predict(input=image_path)
        except Exception as e:
            logger.error(f'PaddleOCR 识别失败: {image_path}, 错误: {e}')
            return []
        return self._convert_results(raw_results)

    @staticmethod
    def _convert_results(raw_results) -> List[OcrTextBlock]:
        """paddleocr 3.x predict 结果（OCRResult 列表，dict-like）→ OcrTextBlock 列表"""
        if not raw_results:
            return []
        first = raw_results[0]
        texts = first.get('rec_texts') or []
        scores = first.get('rec_scores') or []
        polys = first.get('rec_polys')
        if polys is None:
            polys = first.get('dt_polys')
        if polys is None:
            polys = []

        blocks = []
        for text, score, poly in zip(texts, scores, polys):
            if hasattr(poly, 'tolist'):
                poly = poly.tolist()
            blocks.append(OcrTextBlock(text=text, confidence=float(score), bbox=poly))
        return blocks


# 模块级实例（进程内复用），参照 playwright_client 的 playwright_client
paddle_ocr_client = PaddleOcrClient()


def get_paddle_ocr_client():
    """获取 PaddleOcrClient 单例（便捷访问器，参照 get_playwright_client）"""
    return paddle_ocr_client
