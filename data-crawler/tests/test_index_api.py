#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数分析 API 接口测试（TDD）

mock _index_storage 避免连真实库（遵循 conftest 范式），验证 4 个接口的
参数传递与响应结构。纯计算逻辑由 test_index_analysis.py 覆盖。
"""
from unittest.mock import MagicMock

import pytest

from app.web import api_server


# 构造的日线数据（5 条，跨 1/2 月），字段与 IndexInfoStorage._to_dict 一致
MOCK_HISTORY = [
    {'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数',
     'trade_date': '2024-01-02', 'open_price': 100, 'close_price': 100,
     'high_price': 101, 'low_price': 99, 'change_percent': 0.0,
     'volume': 1000, 'amount': 10.0, 'turnover_rate': 0.0,
     'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0},
    {'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数',
     'trade_date': '2024-01-03', 'open_price': 100, 'close_price': 105,
     'high_price': 106, 'low_price': 100, 'change_percent': 5.0,
     'volume': 1200, 'amount': 12.0, 'turnover_rate': 0.0,
     'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0},
    {'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数',
     'trade_date': '2024-01-04', 'open_price': 105, 'close_price': 102,
     'high_price': 106, 'low_price': 101, 'change_percent': -2.8571,
     'volume': 900, 'amount': 9.0, 'turnover_rate': 0.0,
     'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0},
    {'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数',
     'trade_date': '2024-02-01', 'open_price': 102, 'close_price': 110,
     'high_price': 111, 'low_price': 102, 'change_percent': 7.8431,
     'volume': 1500, 'amount': 15.0, 'turnover_rate': 0.0,
     'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0},
    {'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数',
     'trade_date': '2024-02-02', 'open_price': 110, 'close_price': 115,
     'high_price': 116, 'low_price': 110, 'change_percent': 4.5455,
     'volume': 1300, 'amount': 13.0, 'turnover_rate': 0.0,
     'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0},
]


@pytest.fixture
def index_storage(api):
    """注入 mock 指数存储"""
    store = MagicMock()
    api._index_storage = store
    return store


# ==================== /api/indexes 列表 ====================

def test_get_indexes_list(client, index_storage, login, admin_user):
    login(client, admin_user)
    index_storage.get_index_list_with_pagination.return_value = (
        [{'index_code': '000688', 'index_name': '科创50', 'trade_date': '2024-01-02',
          'close_price': 100.0}], 1
    )
    resp = client.get('/api/indexes?page=1&page_size=10&index_code=000688')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total'] == 1
    assert len(data['data']) == 1
    assert data['page'] == 1
    assert data['page_size'] == 10
    # 参数透传到 storage
    call_kwargs = index_storage.get_index_list_with_pagination.call_args.kwargs
    assert call_kwargs['index_code'] == '000688'
    assert call_kwargs['page'] == 1


def test_get_indexes_requires_login(client, index_storage):
    """未登录访问 /api/indexes 返回 401"""
    resp = client.get('/api/indexes')
    assert resp.status_code == 401


# ==================== /api/indexes/options 下拉 ====================

def test_get_index_options(client, index_storage, login, admin_user):
    login(client, admin_user)
    index_storage.get_all_indexes.return_value = [
        {'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数'},
        {'index_code': '000300', 'index_name': '沪深300', 'index_type': '宽基指数'},
    ]
    resp = client.get('/api/indexes/options')

    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['data']) == 2
    assert data['data'][0]['index_code'] == '000688'


# ==================== /api/indexes/analysis 分析 ====================

def test_get_analysis_structure(client, index_storage, login, admin_user):
    login(client, admin_user)
    index_storage.get_index_history.return_value = MOCK_HISTORY
    resp = client.get('/api/indexes/analysis?index_code=000688&start_date=2024-01-01&end_date=2024-02-28')

    assert resp.status_code == 200
    data = resp.get_json()
    # 顶层结构
    assert set(data.keys()) >= {'overview', 'series', 'change_distribution',
                                'monthly_returns', 'ma_signal'}
    # 概览
    ov = data['overview']
    assert ov['count'] == 5
    assert ov['latest_close'] == pytest.approx(115)
    assert ov['latest_date'] == '2024-02-02'
    assert ov['interval_change_pct'] == pytest.approx(15.0, rel=1e-3)  # 100->115
    # series 长度 == 数据量，含均线字段
    assert len(data['series']) == 5
    assert set(data['series'][0].keys()) >= {'date', 'close', 'ma5', 'ma20', 'ma60', 'ma250', 'amount'}
    # ma5 在第 5 条才有值
    assert data['series'][0]['ma5'] is None
    assert data['series'][4]['ma5'] == pytest.approx((100 + 105 + 102 + 110 + 115) / 5)
    # 月度收益：1 月、2 月
    assert len(data['monthly_returns']) == 2
    # 涨跌幅分布非空
    assert len(data['change_distribution']) > 0
    # 均线信号
    assert isinstance(data['ma_signal']['suggestion'], str)
    # 参数透传
    call_kwargs = index_storage.get_index_history.call_args.kwargs
    assert call_kwargs['index_code'] == '000688'


def test_get_analysis_missing_code(client, index_storage, login, admin_user):
    """缺 index_code 返回 400"""
    login(client, admin_user)
    resp = client.get('/api/indexes/analysis')
    assert resp.status_code == 400


def test_get_analysis_warmup(client, index_storage, login, admin_user):
    """均线预热：向前多取历史数据，使区间内首日均线就有值。

    构造 10 条数据 = 5 条预热(2023-11~12) + 5 条区间(2024-01~02)。
    start_date=2024-01-01 -> series 只含区间内 5 条；
    区间首日(2024-01-02)的 MA5 因预热而有值（不预热则 None）。
    """
    login(client, admin_user)
    base = {
        'index_code': '000688', 'index_name': '科创50', 'index_type': '宽基指数',
        'open_price': 100, 'high_price': 101, 'low_price': 99,
        'volume': 1000, 'amount': 10.0, 'turnover_rate': 0.0,
        'pe_ratio': 0.0, 'pe_percentile': 0.0, 'pb_ratio': 0.0,
    }
    # all_closes = [80, 85, 90, 95, 98, 100, 105, 102, 110, 115]
    rows = [
        {**base, 'trade_date': '2023-11-28', 'close_price': 80, 'change_percent': 0.0},
        {**base, 'trade_date': '2023-11-29', 'close_price': 85, 'change_percent': 5.0},
        {**base, 'trade_date': '2023-11-30', 'close_price': 90, 'change_percent': 3.0},
        {**base, 'trade_date': '2023-12-01', 'close_price': 95, 'change_percent': 5.0},
        {**base, 'trade_date': '2023-12-04', 'close_price': 98, 'change_percent': 3.0},
        {**base, 'trade_date': '2024-01-02', 'close_price': 100, 'change_percent': 0.0},
        {**base, 'trade_date': '2024-01-03', 'close_price': 105, 'change_percent': 5.0},
        {**base, 'trade_date': '2024-01-04', 'close_price': 102, 'change_percent': -2.86},
        {**base, 'trade_date': '2024-02-01', 'close_price': 110, 'change_percent': 7.84},
        {**base, 'trade_date': '2024-02-02', 'close_price': 115, 'change_percent': 4.55},
    ]
    index_storage.get_index_history.return_value = rows
    resp = client.get('/api/indexes/analysis?index_code=000688&start_date=2024-01-01&end_date=2024-02-28')

    assert resp.status_code == 200
    data = resp.get_json()
    # series 只含区间内 5 条（预热 5 条不展示）
    assert len(data['series']) == 5
    assert data['series'][0]['date'] == '2024-01-02'
    # 区间首日 MA5 因预热有值：mean([85,90,95,98,100]) = 93.6
    assert data['series'][0]['ma5'] is not None
    assert data['series'][0]['ma5'] == pytest.approx(93.6, rel=1e-6)
    # 概览基于区间内 5 条（不含预热）
    assert data['overview']['count'] == 5
    assert data['overview']['latest_close'] == pytest.approx(115)
    assert data['overview']['interval_change_pct'] == pytest.approx(15.0, rel=1e-3)  # 100->115


def test_get_analysis_empty_data(client, index_storage, login, admin_user):
    """区间无数据返回空结构而非报错"""
    login(client, admin_user)
    index_storage.get_index_history.return_value = []
    resp = client.get('/api/indexes/analysis?index_code=000688')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['overview']['count'] == 0
    assert data['series'] == []
