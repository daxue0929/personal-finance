#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补录撞唯一键时复活软删记录 -- 路由层测试（TDD，红）

覆盖：
1. 软删记录存在 -> 原地复活（不 INSERT），process_buyer_transaction 用原 id
2. 无任何记录 -> 走 INSERT，process_buyer_transaction 用新 id
3. 真正重复（活记录已存在）-> 400 + buy_date 文案

mock 策略：opt-in business_storages_mock + 局部 MagicMock session + patch get_nav_value_by_date
不连真实 MySQL（与 conftest.py 注释一致：项目 .env 指向生产库，绝不在测试中触碰）。
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError


def _build_session(query_first_returns):
    """构造一个 mock session: query().filter().first() 返回 query_first_returns"""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = query_first_returns
    return session


def test_soft_deleted_record_revives(client, business_storages_mock, login, admin_user):
    """软删记录存在 -> 原地复活，不 INSERT"""
    login(client, admin_user)
    mocks = business_storages_mock
    buyer_storage = mocks['_buyer_storage']
    fund_storage = mocks['_fund_storage']

    # 模拟软删记录
    soft_deleted = MagicMock()
    soft_deleted.id = 999
    soft_deleted.del_flag = '0'  # 进来时是 0

    session = _build_session(soft_deleted)
    buyer_storage.Session.return_value = session
    fund_storage.get_fund_by_code.return_value = MagicMock(net_asset_value=1.5)
    buyer_storage.process_buyer_transaction.return_value = 'SUCCESS'

    with patch('app.utils.nav_utils.get_nav_value_by_date', return_value=1.5):
        resp = client.post('/api/buyers/backfill', json={
            'fund_code': '011613',
            'fund_name': '华夏科创50ETF联接C',
            'time': '2026-08-19',
            'amt': 1000,
            'type': '1',
            'remark': ''
        })

    # 201 成功
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data['success'] is True
    assert data['position_updated'] is True

    # 关键：没走 INSERT
    session.add.assert_not_called()
    # 关键：软删记录被原地 UPDATE（del_flag 改 1，buy_status 改 PENDING）
    assert soft_deleted.del_flag == '1'
    assert soft_deleted.buy_status == 'PENDING'

    # process_buyer_transaction 用的是复活的 id
    call_args = buyer_storage.process_buyer_transaction.call_args
    assert call_args.args[0] == [999]


def test_no_deleted_record_inserts(client, business_storages_mock, login, admin_user):
    """无任何记录 -> 走 INSERT，process_buyer_transaction 用新 id"""
    login(client, admin_user)
    mocks = business_storages_mock
    buyer_storage = mocks['_buyer_storage']
    fund_storage = mocks['_fund_storage']

    session = _build_session(None)  # 第一次 query 无软删
    buyer_storage.Session.return_value = session
    fund_storage.get_fund_by_code.return_value = MagicMock(net_asset_value=1.5)
    buyer_storage.process_buyer_transaction.return_value = 'SUCCESS'

    with patch('app.utils.nav_utils.get_nav_value_by_date', return_value=1.5):
        resp = client.post('/api/buyers/backfill', json={
            'fund_code': '011613',
            'fund_name': '华夏科创50ETF联接C',
            'time': '2026-08-19',
            'amt': 1000,
            'type': '1',
            'remark': ''
        })

    assert resp.status_code == 201
    # INSERT 走起
    session.add.assert_called_once()
    # commit + refresh 都被调用
    session.commit.assert_called_once()
    session.refresh.assert_called_once()
    # process_buyer_transaction 被调用
    buyer_storage.process_buyer_transaction.assert_called_once()


def test_true_duplicate_returns_400(client, business_storages_mock, login, admin_user):
    """真正重复（活记录已存在） -> 400 + buy_date 文案"""
    login(client, admin_user)
    mocks = business_storages_mock
    buyer_storage = mocks['_buyer_storage']
    fund_storage = mocks['_fund_storage']

    # 模拟：
    # 1. 首次 query(filter del_flag='0') -> None
    # 2. session.commit 触发 IntegrityError
    # 3. 兜底 query 返活记录
    existing = MagicMock()
    existing.id = 555
    existing.del_flag = '1'

    session = MagicMock()
    first_call = MagicMock()
    first_call.filter.return_value.first.return_value = None
    second_call = MagicMock()
    second_call.filter.return_value.first.return_value = existing
    session.query.side_effect = [first_call, second_call]
    # commit 触发 IntegrityError
    session.commit.side_effect = IntegrityError("mock", {}, None)

    buyer_storage.Session.return_value = session
    fund_storage.get_fund_by_code.return_value = MagicMock(net_asset_value=1.5)

    with patch('app.utils.nav_utils.get_nav_value_by_date', return_value=1.5):
        resp = client.post('/api/buyers/backfill', json={
            'fund_code': '011613',
            'fund_name': '华夏科创50ETF联接C',
            'time': '2026-08-19',
            'amt': 1000,
            'type': '1',
            'remark': ''
        })

    assert resp.status_code == 400
    data = resp.get_json()
    assert '2026-08-19' in data['error']
    # 回滚被调用
    session.rollback.assert_called()
