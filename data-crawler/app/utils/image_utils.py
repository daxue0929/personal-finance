#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 图片上传工具

base64 解码、图片魔数识别、临时文件管理。供 web 进程 OCR 识别接口使用。

设计要点：
- 纯函数 + 上下文管理器，无 OCR/Flask 依赖，可独立单测。
- 原始图片不持久化：save_temp_image 仅供 PaddleOCR 读取文件路径，
  退出 with 块即删除（finally 兜底，含异常路径）。
"""

import base64
import binascii
import os
import tempfile
from contextlib import contextmanager

# 图片魔数 → 后缀（按匹配长度倒序检测，避免短前缀误判）
_MAGIC_SIGNATURES = [
    (b'\x89PNG\r\n\x1a\n', '.png'),
    (b'\xff\xd8\xff', '.jpg'),
    (b'GIF87a', '.gif'),
    (b'GIF89a', '.gif'),
]
# WebP：RIFF 容器，第 8-12 字节为 'WEBP'
_WEBP_MAGIC = (b'RIFF', b'WEBP')


def strip_data_uri_prefix(text: str) -> str:
    """剥离 data URI 前缀（'data:image/png;base64,...' → '...'），非 data: 前缀原样返回"""
    if text.startswith('data:') and ',' in text:
        return text.split(',', 1)[1]
    return text


def decode_base64_image(text: str) -> bytes:
    """base64 字符串 → 图片字节。兼容 data URI 前缀与折行/空格。

    Raises:
        ValueError: 非字符串、空白字符串或非法 base64
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError('images 不能为空')
    cleaned = ''.join(strip_data_uri_prefix(text).split())
    try:
        return base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f'images 不是合法的 base64: {e}')


def detect_image_extension(image_bytes: bytes) -> str:
    """按文件魔数识别图片格式，返回后缀（'.png'/'.jpg'/...）；无法识别返回 None"""
    for magic, ext in _MAGIC_SIGNATURES:
        if image_bytes.startswith(magic):
            return ext
    if (len(image_bytes) >= 12
            and image_bytes.startswith(_WEBP_MAGIC[0])
            and image_bytes[8:12] == _WEBP_MAGIC[1]):
        return '.webp'
    return None


@contextmanager
def save_temp_image(image_bytes: bytes):
    """图片字节写入临时文件供 OCR 读取，退出 with 块即删除（finally 兜底）。

    Yields:
        临时文件路径（后缀按魔数识别）

    Raises:
        ValueError: 字节不是可识别的图片格式
    """
    ext = detect_image_extension(image_bytes)
    if not ext:
        raise ValueError('images 不是可识别的图片格式（支持 png/jpeg/gif/webp）')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        tmp.write(image_bytes)
        tmp.close()
        yield tmp.name
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass  # 文件已被删除或写入前失败，不掩盖业务异常
