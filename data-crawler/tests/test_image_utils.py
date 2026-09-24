#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 图片上传工具测试（TDD）

覆盖 app/utils/image_utils.py：
- strip_data_uri_prefix：data URI 前缀剥离
- decode_base64_image：base64 解码（合法/非法/空/非字符串）
- detect_image_extension：图片魔数识别（png/jpeg/webp/未知）
- save_temp_image：临时文件写入 + finally 必删（正常与异常路径）

均为纯函数/纯文件操作，无 OCR 依赖。
"""
import base64
import os

import pytest

# 1x1 png 图片字节
PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)
JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 100
WEBP_BYTES = b'RIFF' + b'\x00' * 4 + b'WEBP' + b'\x00' * 100


# ==================== strip_data_uri_prefix ====================

def test_strip_data_uri_prefix():
    from app.utils.image_utils import strip_data_uri_prefix
    assert strip_data_uri_prefix('data:image/png;base64,QUJD') == 'QUJD'
    assert strip_data_uri_prefix('data:image/jpeg;base64,QUJD') == 'QUJD'


def test_strip_no_prefix_passthrough():
    from app.utils.image_utils import strip_data_uri_prefix
    assert strip_data_uri_prefix('QUJD') == 'QUJD'


def test_strip_non_data_uri_passthrough():
    """非 data: 前缀但含逗号的字符串原样返回（后续 base64 校验会拦截）"""
    from app.utils.image_utils import strip_data_uri_prefix
    assert strip_data_uri_prefix('http://x,y') == 'http://x,y'


# ==================== decode_base64_image ====================

def test_decode_valid_base64():
    from app.utils.image_utils import decode_base64_image
    assert decode_base64_image(base64.b64encode(PNG_BYTES).decode()) == PNG_BYTES


def test_decode_with_data_uri():
    from app.utils.image_utils import decode_base64_image
    data_uri = 'data:image/png;base64,' + base64.b64encode(PNG_BYTES).decode()
    assert decode_base64_image(data_uri) == PNG_BYTES


def test_decode_with_whitespace():
    """base64 串允许含换行/空格（部分客户端折行输出）"""
    from app.utils.image_utils import decode_base64_image
    b64 = base64.b64encode(PNG_BYTES).decode()
    assert decode_base64_image(b64[:20] + '\n' + b64[20:]) == PNG_BYTES


def test_decode_invalid_base64_raises():
    from app.utils.image_utils import decode_base64_image
    with pytest.raises(ValueError):
        decode_base64_image('!!!not-base64!!!')


def test_decode_empty_raises():
    from app.utils.image_utils import decode_base64_image
    with pytest.raises(ValueError):
        decode_base64_image('')
    with pytest.raises(ValueError):
        decode_base64_image('   ')


def test_decode_non_string_raises():
    from app.utils.image_utils import decode_base64_image
    with pytest.raises(ValueError):
        decode_base64_image(None)
    with pytest.raises(ValueError):
        decode_base64_image(123)


# ==================== detect_image_extension ====================

def test_detect_png():
    from app.utils.image_utils import detect_image_extension
    assert detect_image_extension(PNG_BYTES) == '.png'


def test_detect_jpeg():
    from app.utils.image_utils import detect_image_extension
    assert detect_image_extension(JPEG_BYTES) == '.jpg'


def test_detect_webp():
    from app.utils.image_utils import detect_image_extension
    assert detect_image_extension(WEBP_BYTES) == '.webp'


def test_detect_unknown_returns_none():
    from app.utils.image_utils import detect_image_extension
    assert detect_image_extension(b'plain text content') is None
    assert detect_image_extension(b'') is None


# ==================== save_temp_image ====================

def test_save_temp_image_writes_bytes_and_suffix():
    from app.utils.image_utils import save_temp_image, detect_image_extension
    with save_temp_image(PNG_BYTES) as path:
        assert os.path.exists(path)
        assert path.endswith(detect_image_extension(PNG_BYTES))
        with open(path, 'rb') as f:
            assert f.read() == PNG_BYTES


def test_save_temp_image_deleted_after_normal_exit():
    from app.utils.image_utils import save_temp_image
    with save_temp_image(PNG_BYTES) as path:
        pass
    assert not os.path.exists(path)


def test_save_temp_image_deleted_on_exception():
    from app.utils.image_utils import save_temp_image
    with pytest.raises(RuntimeError):
        with save_temp_image(PNG_BYTES) as path:
            raise RuntimeError('OCR 炸了')
    assert not os.path.exists(path)


def test_save_temp_image_rejects_unknown_format():
    from app.utils.image_utils import save_temp_image
    with pytest.raises(ValueError):
        with save_temp_image(b'not an image'):
            pass
