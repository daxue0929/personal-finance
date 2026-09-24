#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 接口 Basic Auth 模块测试（TDD）

覆盖 app/web/ocr_auth.py：
- parse_basic_auth：Authorization 头解析（合法/缺头/非 Basic/非 base64/无冒号）
- verify_credentials：凭证比对（匹配/不匹配/env 未配置时 fail-closed）
- require_ocr_auth 装饰器：401 拦截 / 放行

凭证通过环境变量 OCR_API_CLIENT_ID / OCR_API_CLIENT_SECRET 注入（monkeypatch）。
"""
import base64

import pytest


def _basic_header(client_id='demo-client', client_secret='demo-secret'):
    token = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
    return f'Basic {token}'


@pytest.fixture
def ocr_env(monkeypatch):
    """注入测试用 OCR 凭证"""
    monkeypatch.setenv('OCR_API_CLIENT_ID', 'demo-client')
    monkeypatch.setenv('OCR_API_CLIENT_SECRET', 'demo-secret')


# ==================== parse_basic_auth ====================

def test_parse_valid_header():
    from app.web.ocr_auth import parse_basic_auth
    assert parse_basic_auth(_basic_header('alice', 's3cret')) == ('alice', 's3cret')


def test_parse_missing_header():
    from app.web.ocr_auth import parse_basic_auth
    assert parse_basic_auth(None) is None
    assert parse_basic_auth('') is None


def test_parse_non_basic_scheme():
    from app.web.ocr_auth import parse_basic_auth
    assert parse_basic_auth('Bearer abc123') is None


def test_parse_non_base64_token():
    from app.web.ocr_auth import parse_basic_auth
    assert parse_basic_auth('Basic !!!not-base64!!!') is None


def test_parse_no_colon_after_decode():
    from app.web.ocr_auth import parse_basic_auth
    token = base64.b64encode('nocolon'.encode()).decode()
    assert parse_basic_auth(f'Basic {token}') is None


def test_parse_empty_client_id():
    from app.web.ocr_auth import parse_basic_auth
    token = base64.b64encode(':secret'.encode()).decode()
    assert parse_basic_auth(f'Basic {token}') is None


def test_parse_secret_may_contain_colon():
    """secret 中允许出现冒号（只按第一个冒号切分）"""
    from app.web.ocr_auth import parse_basic_auth
    token = base64.b64encode('alice:a:b'.encode()).decode()
    assert parse_basic_auth(f'Basic {token}') == ('alice', 'a:b')


def test_parse_scheme_case_insensitive():
    """scheme 大小写不敏感（RFC 7617）"""
    from app.web.ocr_auth import parse_basic_auth
    token = base64.b64encode(b'alice:s3cret').decode()
    assert parse_basic_auth(f'basic {token}') == ('alice', 's3cret')


# ==================== verify_credentials ====================

def test_verify_success(ocr_env):
    from app.web.ocr_auth import verify_credentials
    assert verify_credentials('demo-client', 'demo-secret') is True


def test_verify_wrong_secret(ocr_env):
    from app.web.ocr_auth import verify_credentials
    assert verify_credentials('demo-client', 'wrong') is False


def test_verify_wrong_client_id(ocr_env):
    from app.web.ocr_auth import verify_credentials
    assert verify_credentials('other', 'demo-secret') is False


def test_verify_fail_closed_when_env_missing(monkeypatch):
    """env 未配置凭证时一律拒绝（fail-closed），不允许空凭证通过"""
    monkeypatch.delenv('OCR_API_CLIENT_ID', raising=False)
    monkeypatch.delenv('OCR_API_CLIENT_SECRET', raising=False)
    from app.web.ocr_auth import verify_credentials
    assert verify_credentials('any', 'any') is False
    assert verify_credentials('', '') is False


def test_verify_fail_closed_when_env_partial(monkeypatch):
    """只配置一个时也拒绝"""
    monkeypatch.setenv('OCR_API_CLIENT_ID', 'demo-client')
    monkeypatch.delenv('OCR_API_CLIENT_SECRET', raising=False)
    from app.web.ocr_auth import verify_credentials
    assert verify_credentials('demo-client', 'any') is False


# ==================== require_ocr_auth 装饰器 ====================

def test_decorator_rejects_without_header(ocr_env):
    from flask import Flask
    from app.web.ocr_auth import require_ocr_auth
    app = Flask(__name__)

    @app.route('/protected', methods=['POST'])
    @require_ocr_auth
    def protected():
        return {'ok': True}

    with app.test_client() as c:
        resp = c.post('/protected', json={})
        assert resp.status_code == 401
        assert resp.get_json()['error'] == '认证失败'


def test_decorator_rejects_wrong_credentials(ocr_env):
    from flask import Flask
    from app.web.ocr_auth import require_ocr_auth
    app = Flask(__name__)

    @app.route('/protected', methods=['POST'])
    @require_ocr_auth
    def protected():
        return {'ok': True}

    with app.test_client() as c:
        resp = c.post('/protected', json={},
                      headers={'Authorization': _basic_header('demo-client', 'bad')})
        assert resp.status_code == 401


def test_decorator_passes_with_valid_credentials(ocr_env):
    from flask import Flask
    from app.web.ocr_auth import require_ocr_auth
    app = Flask(__name__)

    @app.route('/protected', methods=['POST'])
    @require_ocr_auth
    def protected():
        return {'ok': True}

    with app.test_client() as c:
        resp = c.post('/protected', json={},
                      headers={'Authorization': _basic_header()})
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
