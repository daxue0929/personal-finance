#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 识别接口测试（TDD）

覆盖 POST /api/ocr/recognize：
- Basic Auth：无凭证/错误凭证 → 401；正确凭证放行
- 参数校验：images 缺失/空/非 base64/非图片 → 400
- 主流程：合法图片 → 200 返回 {count, records}；0 条记录不算错误
- 异常分支：OCR 未安装 ImportError → 503；识别异常 → 500
- 会话登录豁免：该接口不走 session 鉴权（外部系统无 Cookie）

get_paddle_ocr_client 与 AlipayRecordParser 一律 mock，不依赖 paddleocr 安装。
"""
import base64
import json as jsonlib
from unittest.mock import MagicMock, patch

import pytest

from app.parser.alipay_record_parser import AlipayTradeRecord

PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode()
NOT_IMAGE_B64 = base64.b64encode(b'plain text not image').decode()

SAMPLE_RECORDS = [
    AlipayTradeRecord(
        fund_name='华夏科创50ETF联接C(011613)',
        trade_type='定投',
        amount=300.0,
        status='交易进行中',
        trade_time='2026-09-24 11:44:00',
    )
]


def _auth_header(client_id='demo-client', client_secret='demo-secret'):
    token = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
    return {'Authorization': f'Basic {token}'}


@pytest.fixture
def ocr_env(monkeypatch):
    monkeypatch.setenv('OCR_API_CLIENT_ID', 'demo-client')
    monkeypatch.setenv('OCR_API_CLIENT_SECRET', 'demo-secret')


@pytest.fixture
def ocr_mocks(api):
    """mock OCR 引擎与解析器，返回 (ocr_client_mock, parser_cls_mock)"""
    ocr_client = MagicMock()
    ocr_client.recognize.return_value = [MagicMock()]  # 若干文本块
    parser_instance = MagicMock()
    parser_instance.parse.return_value = SAMPLE_RECORDS
    with patch.object(api, 'get_paddle_ocr_client', return_value=ocr_client), \
         patch.object(api, 'AlipayRecordParser', return_value=parser_instance):
        yield ocr_client, parser_instance


# ==================== 认证 ====================

def test_no_authorization_returns_401(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64})
    assert resp.status_code == 401
    assert resp.get_json()['error'] == '认证失败'


def test_wrong_credentials_returns_401(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                       headers=_auth_header('demo-client', 'bad-secret'))
    assert resp.status_code == 401


def test_no_session_login_required(client, ocr_env, ocr_mocks):
    """该接口用 Basic Auth，不需要会话 Cookie（session 未登录也应放行）"""
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                       headers=_auth_header())
    assert resp.status_code == 200


# ==================== 参数校验 ====================

def test_missing_images_returns_400(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={}, headers=_auth_header())
    assert resp.status_code == 400
    assert 'error' in resp.get_json()


def test_empty_images_returns_400(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={'images': '  '}, headers=_auth_header())
    assert resp.status_code == 400


def test_non_string_images_returns_400(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={'images': [PNG_B64]}, headers=_auth_header())
    assert resp.status_code == 400


def test_invalid_base64_returns_400(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={'images': '!!!bad!!!'}, headers=_auth_header())
    assert resp.status_code == 400
    assert 'base64' in resp.get_json()['error']


def test_non_image_bytes_returns_400(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize', json={'images': NOT_IMAGE_B64}, headers=_auth_header())
    assert resp.status_code == 400
    assert '图片' in resp.get_json()['error']


# ==================== 主流程 ====================

def test_recognize_success_returns_records(client, api, ocr_env, ocr_mocks):
    ocr_client, parser_instance = ocr_mocks
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                       headers=_auth_header())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['count'] == 1
    record = body['records'][0]
    assert record['fund_name'] == '华夏科创50ETF联接C(011613)'
    assert record['trade_type'] == '定投'
    assert record['amount'] == 300.0
    assert record['status'] == '交易进行中'
    assert record['trade_time'] == '2026-09-24 11:44:00'
    # OCR 引擎确实被调用，且传入的是临时文件路径
    assert ocr_client.recognize.call_count == 1
    tmp_path = ocr_client.recognize.call_args[0][0]
    assert isinstance(tmp_path, str) and tmp_path.endswith('.png')


def test_recognize_with_data_uri_prefix(client, ocr_env, ocr_mocks):
    resp = client.post('/api/ocr/recognize',
                       json={'images': 'data:image/png;base64,' + PNG_B64},
                       headers=_auth_header())
    assert resp.status_code == 200


def test_recognize_zero_records_is_not_error(client, ocr_env, ocr_mocks):
    """识别出 0 条记录（图片不含交易记录）正常返回 200，不算错误"""
    _, parser_instance = ocr_mocks
    parser_instance.parse.return_value = []
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                       headers=_auth_header())
    assert resp.status_code == 200
    assert resp.get_json() == {'count': 0, 'records': []}


def test_recognize_result_logged_as_json(client, api, ocr_env, ocr_mocks):
    """识别结果以 JSON 形式打印 INFO 日志，且日志不含 base64 原文。

    项目 logger 不 propagate（caplog 捕获不到），改为 patch api_server.logger。
    """
    mock_logger = MagicMock()
    with patch.object(api, 'logger', mock_logger):
        resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                           headers=_auth_header())
    assert resp.status_code == 200
    info_msgs = ' '.join(str(call) for call in mock_logger.info.call_args_list)
    assert 'OCR 识别结果' in info_msgs
    assert '011613' in info_msgs  # 结果 JSON 内容
    assert PNG_B64 not in info_msgs  # base64 原文不进日志


# ==================== 异常分支 ====================

def test_ocr_not_installed_returns_503(client, ocr_env, ocr_mocks):
    ocr_client, _ = ocr_mocks
    ocr_client.recognize.side_effect = ImportError('未安装 paddleocr')
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                       headers=_auth_header())
    assert resp.status_code == 503
    assert 'OCR' in resp.get_json()['error']


def test_recognize_exception_returns_500(client, ocr_env, ocr_mocks):
    ocr_client, _ = ocr_mocks
    ocr_client.recognize.side_effect = RuntimeError('引擎崩溃')
    resp = client.post('/api/ocr/recognize', json={'images': PNG_B64},
                       headers=_auth_header())
    assert resp.status_code == 500
    assert 'error' in resp.get_json()


def test_oversized_body_returns_413(client, api, ocr_env, ocr_mocks):
    """超过 MAX_CONTENT_LENGTH 的请求体被 Flask 拦截为 413"""
    api.app.config['MAX_CONTENT_LENGTH'] = 1024
    try:
        resp = client.post('/api/ocr/recognize',
                           data=jsonlib.dumps({'images': 'x' * 2048}),
                           content_type='application/json',
                           headers=_auth_header())
        assert resp.status_code == 413
    finally:
        api.app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024
