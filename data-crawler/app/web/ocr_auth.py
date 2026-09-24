#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 对外开放接口的 Basic Auth 认证模块

独立于会话登录鉴权（require_auth 钩子），供无 Cookie 的外部系统调用。
凭证配置在 .env：OCR_API_CLIENT_ID / OCR_API_CLIENT_SECRET。

设计要点：
- fail-closed：env 未配置凭证时一律拒绝，不允许空凭证通过。
- 比对用 hmac.compare_digest，防时序攻击。
- 凭证每次请求时读取 env（不缓存），改配置重启即生效，且便于测试 monkeypatch。
"""

import base64
import binascii
import functools
import hmac
import os

from flask import jsonify, request


def get_ocr_credentials():
    """从环境变量读取 OCR 接口凭证，返回 (client_id, client_secret)；未配置返回 (None, None)"""
    return os.getenv('OCR_API_CLIENT_ID'), os.getenv('OCR_API_CLIENT_SECRET')


def parse_basic_auth(header):
    """解析 'Basic base64(clientId:clientSecret)' 头，返回 (client_id, client_secret)；非法返回 None。

    secret 中允许出现冒号（只按第一个冒号切分）；scheme 大小写不敏感（RFC 7617）。
    """
    if not header:
        return None
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'basic' or not token:
        return None
    try:
        decoded = base64.b64decode(token, validate=True).decode('utf-8')
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    client_id, sep, client_secret = decoded.partition(':')
    if not sep or not client_id:
        return None
    return client_id, client_secret


def verify_credentials(client_id, client_secret):
    """与 .env 配置的凭证比对（fail-closed + compare_digest 防时序攻击）"""
    expected_id, expected_secret = get_ocr_credentials()
    if not expected_id or not expected_secret:
        return False
    return (hmac.compare_digest(client_id, expected_id)
            and hmac.compare_digest(client_secret, expected_secret))


def require_ocr_auth(func):
    """Basic Auth 装饰器：认证失败返回 401，成功放行"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        credentials = parse_basic_auth(request.headers.get('Authorization'))
        if not credentials or not verify_credentials(*credentials):
            return jsonify({'error': '认证失败'}), 401
        return func(*args, **kwargs)
    return wrapper
