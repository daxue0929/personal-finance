#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数基础管理 API 接口测试（TDD）

mock _index_basic_storage 避免连真实库，验证 6 路由的参数传递、响应结构与权限。
"""
from unittest.mock import MagicMock

import pytest

from app.web import api_server


@pytest.fixture
def index_basic_storage(api):
    """注入 mock 指数基础存储"""
    store = MagicMock()
    api._index_basic_storage = store
    return store


# ==================== GET 列表 ====================

def test_list_endpoint_returns_enabled_by_default(client, index_basic_storage, login, admin_user):
    """GET /api/index-basics 默认 include_disabled=False，透传给 storage"""
    login(client, admin_user)
    fake_row = MagicMock(index_code='000300', index_name='沪深300', market='sh',
                         index_type='宽基指数', enabled=1, del_flag='1',
                         create_time=None, update_time=None)
    index_basic_storage.list_all.return_value = ([fake_row], 1)

    resp = client.get('/api/index-basics?include_disabled=false&page=1&page_size=20')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] == 1
    assert len(data['data']) == 1
    # 参数透传
    call_kwargs = index_basic_storage.list_all.call_args.kwargs
    assert call_kwargs.get('include_disabled') is False


def test_list_endpoint_with_include_disabled_true(client, index_basic_storage, login, admin_user):
    """GET /api/index-basics?include_disabled=true 透传 include_disabled=True"""
    login(client, admin_user)
    index_basic_storage.list_all.return_value = ([], 0)

    resp = client.get('/api/index-basics?include_disabled=true')

    assert resp.status_code == 200
    call_kwargs = index_basic_storage.list_all.call_args.kwargs
    assert call_kwargs.get('include_disabled') is True


def test_list_endpoint_pagination_passthrough(client, index_basic_storage, login, admin_user):
    """GET /api/index-basics?page=2&page_size=10 透传分页参数"""
    login(client, admin_user)
    index_basic_storage.list_all.return_value = ([], 0)

    resp = client.get('/api/index-basics?page=2&page_size=10')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['page'] == 2
    assert data['page_size'] == 10
    call_kwargs = index_basic_storage.list_all.call_args.kwargs
    assert call_kwargs.get('page') == 2
    assert call_kwargs.get('page_size') == 10


def test_list_endpoint_filter_passthrough(client, index_basic_storage, login, admin_user):
    """GET /api/index-basics?index_code=000300&index_type=宽基指数 透传过滤"""
    login(client, admin_user)
    index_basic_storage.list_all.return_value = ([], 0)

    resp = client.get('/api/index-basics?index_code=000300&index_type=宽基指数')

    assert resp.status_code == 200
    call_kwargs = index_basic_storage.list_all.call_args.kwargs
    assert call_kwargs.get('index_code') == '000300'
    assert call_kwargs.get('index_type') == '宽基指数'


def test_list_endpoint_empty_filter_treated_as_none(client, index_basic_storage, login, admin_user):
    """空字符串过滤参数当 None 透传（避免误过滤）"""
    login(client, admin_user)
    index_basic_storage.list_all.return_value = ([], 0)

    resp = client.get('/api/index-basics?index_code=&index_type=')

    assert resp.status_code == 200
    call_kwargs = index_basic_storage.list_all.call_args.kwargs
    assert call_kwargs.get('index_code') is None
    assert call_kwargs.get('index_type') is None


def test_list_endpoint_invalid_page_returns_400(client, index_basic_storage, login, admin_user):
    """page=abc 返 400（不是 500）"""
    login(client, admin_user)
    resp = client.get('/api/index-basics?page=abc')
    assert resp.status_code == 400


def test_list_endpoint_requires_login(client, index_basic_storage):
    """未登录访问 /api/index-basics 返回 401"""
    resp = client.get('/api/index-basics')
    assert resp.status_code == 401


# ==================== GET 详情 ====================

def test_get_endpoint_returns_200_for_existing(client, index_basic_storage, login, admin_user):
    """GET /api/index-basics/<code> 存在时 200 + 数据"""
    login(client, admin_user)
    fake_row = MagicMock()
    fake_row.index_code = '000300'
    fake_row.index_name = '沪深300'
    fake_row.market = 'sh'
    fake_row.index_type = '宽基指数'
    fake_row.enabled = 1
    fake_row.del_flag = '1'
    fake_row.create_time = None
    fake_row.update_time = None
    index_basic_storage.get.return_value = fake_row

    resp = client.get('/api/index-basics/000300')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['data']['index_code'] == '000300'
    assert data['data']['index_name'] == '沪深300'
    # 参数透传
    index_basic_storage.get.assert_called_once_with('000300')


def test_get_endpoint_returns_404_for_missing(client, index_basic_storage, login, admin_user):
    """GET /api/index-basics/<code> 不存在时 404"""
    login(client, admin_user)
    index_basic_storage.get.return_value = None

    resp = client.get('/api/index-basics/999999')

    assert resp.status_code == 404


# ==================== POST 新增 ====================

def test_create_endpoint_rejects_invalid_market(client, index_basic_storage, login, admin_user):
    """POST /api/index-basics body.market='xx' 返 400"""
    login(client, admin_user)
    # 模拟 storage.create 抛 ValueError
    index_basic_storage.create.side_effect = ValueError("market 必须是 'sh' 或 'sz', got 'xx'")

    resp = client.post('/api/index-basics', json={
        'index_code': '000300',
        'market': 'xx',
        'index_name': '沪深300',
    })

    assert resp.status_code == 400
    data = resp.get_json()
    assert 'error' in data
    assert 'market' in data['error']


def test_create_endpoint_success(client, index_basic_storage, login, admin_user):
    """POST /api/index-basics 合法数据 201 + success"""
    login(client, admin_user)
    index_basic_storage.create.return_value = True

    resp = client.post('/api/index-basics', json={
        'index_code': '000300',
        'market': 'sh',
        'index_name': '沪深300',
        'index_type': '宽基指数',
        'enabled': 1,
    })

    assert resp.status_code in (200, 201)
    data = resp.get_json()
    assert data['success'] is True
    # body 透传
    call_args = index_basic_storage.create.call_args.args
    assert call_args[0]['index_code'] == '000300'


# ==================== PUT 编辑 ====================

def test_update_endpoint_ignores_index_code_in_body(client, index_basic_storage, login, admin_user):
    """PUT /api/index-basics/<code> body.index_code 应被忽略（白名单外）"""
    login(client, admin_user)
    index_basic_storage.update.return_value = True

    resp = client.put('/api/index-basics/000300', json={
        'index_code': '999999',  # 主键，不应改
        'index_name': '沪深300指数',
    })

    assert resp.status_code == 200
    # URL 路径的 code 透传
    call_args = index_basic_storage.update.call_args
    assert call_args.args[0] == '000300'  # index_code from URL
    # body 里 index_code 应被过滤掉
    update_data = call_args.args[1]
    assert 'index_code' not in update_data
    assert update_data['index_name'] == '沪深300指数'


def test_update_endpoint_returns_404_when_missing(client, index_basic_storage, login, admin_user):
    """PUT /api/index-basics/<code> storage.update 返 False 返 404"""
    login(client, admin_user)
    index_basic_storage.update.return_value = False

    resp = client.put('/api/index-basics/999999', json={
        'index_name': '改名',
    })

    assert resp.status_code == 404


# ==================== DELETE 软删 ====================

def test_delete_endpoint_calls_soft_delete(client, index_basic_storage, login, admin_user):
    """DELETE /api/index-basics/<code> 调 storage.soft_delete"""
    login(client, admin_user)
    index_basic_storage.soft_delete.return_value = True

    resp = client.delete('/api/index-basics/000300')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    index_basic_storage.soft_delete.assert_called_once_with('000300')


def test_delete_endpoint_returns_404_when_missing(client, index_basic_storage, login, admin_user):
    """DELETE /api/index-basics/<code> 不存在 返 404"""
    login(client, admin_user)
    index_basic_storage.soft_delete.return_value = False

    resp = client.delete('/api/index-basics/999999')

    assert resp.status_code == 404


# ==================== POST toggle ====================

def test_toggle_endpoint_updates_enabled(client, index_basic_storage, login, admin_user):
    """POST /api/index-basics/<code>/toggle body.enabled=0 调 storage.toggle_enabled"""
    login(client, admin_user)
    index_basic_storage.toggle_enabled.return_value = True

    resp = client.post('/api/index-basics/000300/toggle', json={'enabled': 0})

    assert resp.status_code == 200
    # 参数透传：index_code + enabled=False
    call_args = index_basic_storage.toggle_enabled.call_args
    assert call_args.args[0] == '000300'
    assert call_args.args[1] is False  # 0 → False


def test_toggle_endpoint_returns_404_when_missing(client, index_basic_storage, login, admin_user):
    """POST /api/index-basics/<code>/toggle 不存在 返 404"""
    login(client, admin_user)
    index_basic_storage.toggle_enabled.return_value = False

    resp = client.post('/api/index-basics/999999/toggle', json={'enabled': 1})

    assert resp.status_code == 404


def test_toggle_endpoint_invalid_enabled_returns_400(client, index_basic_storage, login, admin_user):
    """POST toggle body.enabled='abc' 返 400（不是 500）"""
    login(client, admin_user)
    resp = client.post('/api/index-basics/000300/toggle', json={'enabled': 'abc'})
    assert resp.status_code == 400
    assert 'enabled' in resp.get_json()['error']


def test_toggle_endpoint_value_2_returns_400(client, index_basic_storage, login, admin_user):
    """POST toggle body.enabled=2 返 400（值域校验）"""
    login(client, admin_user)
    resp = client.post('/api/index-basics/000300/toggle', json={'enabled': 2})
    assert resp.status_code == 400
