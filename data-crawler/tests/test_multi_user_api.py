"""
multi-user 功能 HTTP API 测试（PRD multi-user AC-3,4,5,6,7 T4）

TDD：先写预期行为，再由实现满足。
覆盖：
- AC-3: /api/signup 公开端点
- AC-4: /api/me PUT 自我更新
- AC-2: /api/invite-codes 增删查（admin only）
- AC-5: /api/admin/impersonate admin 切换视角
- AC-6: 业务路由 user_id 过滤（buyer/position/portfolio/seller/snapshot/dip_plan）
"""
from unittest.mock import MagicMock, patch


# ==================== AC-3: /api/signup 公开 ====================

def test_signup_creates_user_with_valid_invite(client, api):
    """公开端点：有效邀请码 → 创建 user + 返回 user 字典"""
    invite_storage_mock = MagicMock()
    invite_storage_mock.validate.return_value = {
        'id': 5, 'code': 'ABCD1234', 'created_by': 1,
    }
    api._invite_code_storage = invite_storage_mock

    fake_user = {'id': 10, 'username': 'alice', 'role': 'user', 'enabled': True}

    with patch('app.task.register_user_via_invite.register_user_via_invite',
               return_value=fake_user) as mock_task:
        resp = client.post('/api/signup', json={
            'username': 'alice', 'password': 'pw', 'display_name': 'Alice',
            'invite_code': 'ABCD1234',
        })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body['success'] is True
    assert body['user']['username'] == 'alice'
    mock_task.assert_called_once()


def test_signup_invalid_invite_returns_400(client, api):
    """无效邀请码 → 400 + 不创建 user"""
    invite_storage_mock = MagicMock()
    invite_storage_mock.validate.return_value = None
    api._invite_code_storage = invite_storage_mock

    with patch('app.task.register_user_via_invite.register_user_via_invite',
               side_effect=ValueError('邀请码无效、已过期或已被使用')):
        resp = client.post('/api/signup', json={
            'username': 'bob', 'password': 'pw', 'display_name': '',
            'invite_code': 'BADCODE',
        })

    assert resp.status_code == 400
    assert '邀请码' in resp.get_json()['error']


def test_signup_missing_fields_returns_400(client):
    """缺字段（username/password/invite_code）→ 400"""
    resp = client.post('/api/signup', json={'username': 'alice'})
    assert resp.status_code == 400


# ==================== AC-4: /api/me PUT ====================

def test_update_me_changes_display_name(client, api, normal_user, login):
    """登录后 PUT /api/me 可更新 display_name / password"""
    login(client, normal_user)
    api._user_storage.update_user.return_value = True

    resp = client.put('/api/me', json={'display_name': '新昵称'})
    assert resp.status_code == 200
    call_args = api._user_storage.update_user.call_args
    # 第一个位置参数必须是当前 user id
    assert call_args.args[0] == normal_user['id']
    # 第二个参数是 data dict
    assert call_args.args[1]['display_name'] == '新昵称'


def test_update_me_cannot_change_role_or_enabled(client, api, normal_user, login):
    """普通 user 调用 PUT /api/me 不能改 role/enabled（防提权）"""
    login(client, normal_user)
    resp = client.put('/api/me', json={'role': 'admin', 'enabled': False})
    # 应拒绝（400 或 403）
    assert resp.status_code in (400, 403)
    # update_user 未被调，或被调时 role/enabled 不在 data 里
    if api._user_storage.update_user.called:
        data = api._user_storage.update_user.call_args.args[1]
        assert 'role' not in data
        assert 'enabled' not in data


# ==================== AC-2: /api/invite-codes admin only ====================

def test_list_invite_codes_requires_admin(client, api, normal_user, login, business_storages_mock):
    """普通 user 调 GET /api/invite-codes → 403"""
    login(client, normal_user)
    resp = client.get('/api/invite-codes')
    assert resp.status_code == 403


def test_list_invite_codes_as_admin(client, api, admin_user, login, business_storages_mock):
    """admin 调 GET /api/invite-codes → 200 + 返自己生成的码"""
    api._invite_code_storage = business_storages_mock.get('_invite_code_storage', MagicMock())
    api._invite_code_storage.list_by_admin.return_value = (
        [{'id': 1, 'code': 'ABCD1234', 'created_by': 1}], 1
    )
    login(client, admin_user)
    resp = client.get('/api/invite-codes')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total'] == 1
    assert body['data'][0]['code'] == 'ABCD1234'
    # 应按当前 admin id 过滤（list_by_admin 用 admin_id= 关键字）
    kwargs = api._invite_code_storage.list_by_admin.call_args.kwargs
    assert kwargs['admin_id'] == admin_user['id']


def test_create_invite_code_as_admin(client, api, admin_user, login, business_storages_mock):
    """admin 调 POST /api/invite-codes → 201 + 返新码"""
    api._invite_code_storage = business_storages_mock.get('_invite_code_storage', MagicMock())
    api._invite_code_storage.create.return_value = 'NEW12345'
    login(client, admin_user)
    resp = client.post('/api/invite-codes', json={'ttl_days': 14})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['code'] == 'NEW12345'
    kwargs = api._invite_code_storage.create.call_args.kwargs
    assert kwargs['admin_id'] == admin_user['id']


# ==================== AC-5: admin 切换 user 视角 ====================

def _setup_multi_user_lookup(api, admin_user, normal_user):
    """让 _user_storage.get_user_by_id 区分 admin vs normal。"""
    def fake_get_user_by_id(uid):
        if uid == admin_user['id']:
            return admin_user
        if uid == normal_user['id']:
            return normal_user
        return None
    api._user_storage.get_user_by_id.side_effect = fake_get_user_by_id


def test_impersonate_sets_session(client, api, admin_user, normal_user, login):
    """admin POST /api/admin/impersonate → session 写入 impersonate_user_id"""
    _setup_multi_user_lookup(api, admin_user, normal_user)
    login(client, admin_user)
    resp = client.post('/api/admin/impersonate', json={'user_id': normal_user['id']})
    assert resp.status_code == 200, resp.get_json()
    with client.session_transaction() as sess:
        assert sess.get('impersonate_user_id') == normal_user['id']


def test_impersonate_requires_admin(client, api, normal_user, login):
    """普通 user 调 impersonate → 403"""
    login(client, normal_user)
    resp = client.post('/api/admin/impersonate', json={'user_id': 1})
    assert resp.status_code == 403


def test_stop_impersonate_clears_session(client, api, admin_user, normal_user, login):
    """admin DELETE /api/admin/impersonate → 清除 session 切换"""
    login(client, admin_user)
    with client.session_transaction() as sess:
        sess['impersonate_user_id'] = normal_user['id']
    resp = client.delete('/api/admin/impersonate')
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get('impersonate_user_id') is None


def test_get_me_reflects_impersonation(client, api, admin_user, normal_user, login):
    """admin 切换视角后 GET /api/me 应返 target user 字典"""
    _setup_multi_user_lookup(api, admin_user, normal_user)
    login(client, admin_user)
    with client.session_transaction() as sess:
        sess['impersonate_user_id'] = normal_user['id']
    resp = client.get('/api/me')
    assert resp.status_code == 200
    assert resp.get_json()['user']['username'] == normal_user['username']


# ==================== AC-6: 业务路由 user_id 过滤 ====================

def test_buyers_route_passes_user_id_to_storage(client, api, normal_user, login, business_storages_mock):
    """GET /api/buyers 应把当前 user.id 透传给 storage"""
    login(client, normal_user)
    business_storages_mock['_buyer_storage'].get_buyers_with_pagination.return_value = ([], 0)
    resp = client.get('/api/buyers')
    assert resp.status_code == 200
    kwargs = business_storages_mock['_buyer_storage'].get_buyers_with_pagination.call_args.kwargs
    assert kwargs['user_id'] == normal_user['id']


def test_positions_route_passes_user_id_to_storage(client, api, normal_user, login, business_storages_mock):
    """GET /api/positions 应把当前 user.id 透传给 storage"""
    login(client, normal_user)
    business_storages_mock['_position_storage'].get_positions_with_pagination.return_value = ([], 0)
    resp = client.get('/api/positions')
    assert resp.status_code == 200
    kwargs = business_storages_mock['_position_storage'].get_positions_with_pagination.call_args.kwargs
    assert kwargs['user_id'] == normal_user['id']


def test_portfolios_route_passes_user_id_to_storage(client, api, normal_user, login, business_storages_mock):
    """GET /api/portfolios 应把当前 user.id 透传给 storage"""
    login(client, normal_user)
    business_storages_mock['_portfolio_storage'].get_portfolios_with_pagination.return_value = ([], 0)
    resp = client.get('/api/portfolios')
    assert resp.status_code == 200
    kwargs = business_storages_mock['_portfolio_storage'].get_portfolios_with_pagination.call_args.kwargs
    assert kwargs['user_id'] == normal_user['id']


def test_sellers_route_passes_user_id_to_storage(client, api, normal_user, login, business_storages_mock):
    """GET /api/sellers 应把当前 user.id 透传给 storage"""
    login(client, normal_user)
    business_storages_mock['_seller_storage'].get_sellers_with_pagination.return_value = ([], 0)
    resp = client.get('/api/sellers')
    assert resp.status_code == 200
    kwargs = business_storages_mock['_seller_storage'].get_sellers_with_pagination.call_args.kwargs
    assert kwargs['user_id'] == normal_user['id']


def test_snapshots_route_passes_user_id_to_storage(client, api, normal_user, login, business_storages_mock):
    """GET /api/positions/snapshots 应把当前 user.id 透传给 storage"""
    login(client, normal_user)
    business_storages_mock['_position_snapshot_storage'].get_snapshots_with_pagination.return_value = ([], 0)
    resp = client.get('/api/positions/snapshots')
    assert resp.status_code == 200
    kwargs = business_storages_mock['_position_snapshot_storage'].get_snapshots_with_pagination.call_args.kwargs
    assert kwargs['user_id'] == normal_user['id']


def test_admin_sees_all_users_data(client, api, admin_user, login, business_storages_mock):
    """admin 不切换视角时，业务路由 user_id 应为 None（看所有）"""
    login(client, admin_user)
    business_storages_mock['_position_storage'].get_positions_with_pagination.return_value = ([], 0)
    resp = client.get('/api/positions')
    assert resp.status_code == 200
    kwargs = business_storages_mock['_position_storage'].get_positions_with_pagination.call_args.kwargs
    assert kwargs['user_id'] is None
