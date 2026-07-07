"""
用户登录与用户管理：HTTP 层 + 鉴权 + 权限 + 防自锁 测试

TDD：先写预期行为，再由实现满足。
"""


# ---------- 鉴权中间件 ----------

def test_unauthenticated_api_returns_401(client):
    """未登录访问任意 /api/*（除 /api/login）应返回 401"""
    resp = client.get('/api/funds')
    assert resp.status_code == 401
    assert 'error' in resp.get_json()


def test_health_is_public(client):
    """/health 不在 /api 下，无需登录"""
    resp = client.get('/health')
    assert resp.status_code == 200


def test_login_endpoint_is_public(client, api):
    """未登录也可访问 /api/login（否则永远无法登录）"""
    # verify_user 返回 None 表示凭证错误，应 401 而非「未登录」
    api._user_storage.verify_user.return_value = None
    resp = client.post('/api/login', json={'username': 'x', 'password': 'y'})
    assert resp.status_code == 401


# ---------- 登录 ----------

def test_login_success_returns_user(client, api, admin_user):
    api._user_storage.verify_user.return_value = admin_user
    resp = client.post('/api/login', json={'username': 'admin', 'password': 'secret'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['user']['username'] == 'admin'
    assert body['user']['role'] == 'admin'
    assert 'password' not in str(body)  # 不泄露密码字段


def test_login_sets_cookie(client, api, admin_user):
    api._user_storage.verify_user.return_value = admin_user
    client.post('/api/login', json={'username': 'admin', 'password': 'secret'})
    # Flask test_client 保留 cookie；session cookie 应已种下
    with client.session_transaction() as sess:
        assert sess.get('user_id') == admin_user['id']


def test_login_wrong_password_401(client, api):
    api._user_storage.verify_user.return_value = None
    resp = client.post('/api/login', json={'username': 'admin', 'password': 'bad'})
    assert resp.status_code == 401
    assert resp.get_json()['error'] == '用户名或密码错误'


def test_login_missing_fields_400(client):
    resp = client.post('/api/login', json={})
    assert resp.status_code == 400


def test_login_disabled_user_rejected(client, api):
    """verify_user 只返回启用用户（Storage 层保证），禁用用户登录失败"""
    api._user_storage.verify_user.return_value = None
    resp = client.post('/api/login', json={'username': 'disabled', 'password': 'x'})
    assert resp.status_code == 401


# ---------- /api/me ----------

def test_me_after_login(client, api, admin_user, login):
    login(client, admin_user)
    resp = client.get('/api/me')
    assert resp.status_code == 200
    assert resp.get_json()['user']['username'] == 'admin'


def test_me_without_login_401(client):
    resp = client.get('/api/me')
    assert resp.status_code == 401


def test_logout_clears_session(client, api, admin_user, login):
    login(client, admin_user)
    resp = client.post('/api/logout')
    assert resp.status_code == 200
    # 登出后再访问 /api/me 应 401
    resp2 = client.get('/api/me')
    assert resp2.status_code == 401


def test_disabled_user_session_invalidated(client, api, admin_user, login):
    """已登录用户被禁用后，下次请求立即失效"""
    login(client, admin_user)
    # 模拟管理员随后禁用了该用户
    api._user_storage.get_user_by_id.return_value = {**admin_user, 'enabled': False}
    resp = client.get('/api/me')
    assert resp.status_code == 401


# ---------- 权限：仅管理员可管理用户 ----------

def test_non_admin_cannot_list_users(client, api, normal_user, login):
    login(client, normal_user)
    resp = client.get('/api/users')
    assert resp.status_code == 403


def test_admin_can_list_users(client, api, admin_user, login):
    login(client, admin_user)
    api._user_storage.get_users_with_pagination.return_value = ([admin_user], 1)
    resp = client.get('/api/users')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total'] == 1
    assert isinstance(body['data'], list)


def test_non_admin_cannot_create_user(client, api, normal_user, login):
    login(client, normal_user)
    resp = client.post('/api/users', json={'username': 'a', 'password': 'b'})
    assert resp.status_code == 403


# ---------- 用户 CRUD ----------

def test_create_user_success(client, api, admin_user, login):
    login(client, admin_user)
    new_user = {**admin_user, 'id': 5, 'username': 'newbie', 'role': 'user'}
    api._user_storage.create_user.return_value = new_user
    resp = client.post('/api/users', json={
        'username': 'newbie', 'password': 'pass', 'role': 'user'
    })
    assert resp.status_code == 201
    assert resp.get_json()['success'] is True


def test_create_user_requires_username_and_password(client, api, admin_user, login):
    login(client, admin_user)
    resp = client.post('/api/users', json={'username': 'only_name'})
    assert resp.status_code == 400


def test_create_duplicate_username_400(client, api, admin_user, login):
    login(client, admin_user)
    api._user_storage.create_user.side_effect = ValueError('用户名已存在')
    resp = client.post('/api/users', json={'username': 'admin', 'password': 'x'})
    assert resp.status_code == 400
    assert '存在' in resp.get_json()['error']


def test_update_user_success(client, api, admin_user, login):
    login(client, admin_user)
    api._user_storage.update_user.return_value = True
    resp = client.put('/api/users/2', json={'display_name': '新名字'})
    assert resp.status_code == 200
    api._user_storage.update_user.assert_called_once()


def test_update_user_not_found_404(client, api, admin_user, login):
    login(client, admin_user)
    api._user_storage.update_user.return_value = False
    resp = client.put('/api/users/999', json={'display_name': 'x'})
    assert resp.status_code == 404


def test_delete_user_success(client, api, admin_user, login):
    login(client, admin_user)
    api._user_storage.delete_user.return_value = True
    resp = client.delete('/api/users/2')
    assert resp.status_code == 200
    api._user_storage.delete_user.assert_called_once_with(2)


# ---------- 防自锁：管理员不能对自己做危险操作 ----------

def test_admin_cannot_delete_self(client, api, admin_user, login):
    login(client, admin_user)  # admin_user id=1
    resp = client.delete('/api/users/1')
    assert resp.status_code == 403
    api._user_storage.delete_user.assert_not_called()


def test_admin_cannot_disable_self(client, api, admin_user, login):
    login(client, admin_user)
    resp = client.put('/api/users/1', json={'enabled': False})
    assert resp.status_code == 403
    api._user_storage.update_user.assert_not_called()


def test_admin_cannot_disable_self_via_empty_string(client, api, admin_user, login):
    """防自锁覆盖 falsy 边界：enabled='' 也应被拦截（不能绕过）"""
    login(client, admin_user)
    resp = client.put('/api/users/1', json={'enabled': ''})
    assert resp.status_code == 403
    api._user_storage.update_user.assert_not_called()


def test_admin_cannot_downgrade_self(client, api, admin_user, login):
    login(client, admin_user)
    resp = client.put('/api/users/1', json={'role': 'user'})
    assert resp.status_code == 403
    api._user_storage.update_user.assert_not_called()


def test_admin_cannot_downgrade_self_via_empty_role(client, api, admin_user, login):
    """防自锁覆盖 falsy 边界：role='' / null 也应被拦截（不能绕过）"""
    login(client, admin_user)
    resp = client.put('/api/users/1', json={'role': ''})
    assert resp.status_code == 403
    api._user_storage.update_user.assert_not_called()


def test_admin_can_edit_other_role(client, api, admin_user, login):
    """对他人修改角色/状态应放行"""
    login(client, admin_user)
    api._user_storage.update_user.return_value = True
    resp = client.put('/api/users/2', json={'role': 'user', 'enabled': False})
    assert resp.status_code == 200
