"""
用户登录与用户管理：补充边界测试

覆盖 test_auth.py 未涉及的场景：
- /api/me 对普通用户开放（非 admin_only）
- 创建用户：前端字段透传给 storage（含 create_by=当前管理员）
- 防自锁白名单：管理员可改自己密码（仅拦 enabled/role，不拦 password）
- 更新密码透传到 storage
- _to_dict 不泄露敏感字段（纯函数，不连库）
- 未登录 logout 返回 401
- 用户列表 enabled 过滤参数透传
"""

from app.storage.user_storage import User, _to_dict


# ---------- /api/me 对普通用户开放 ----------

def test_normal_user_can_access_me(client, api, normal_user, login):
    """/api/me 非 admin_only，普通用户也能查看自己信息"""
    login(client, normal_user)
    resp = client.get('/api/me')
    assert resp.status_code == 200
    assert resp.get_json()['user']['username'] == 'lily'


# ---------- 创建用户：字段透传 ----------

def test_create_user_passes_fields_to_storage(client, api, admin_user, login):
    """前端提交的 role/enabled/display_name/session_ttl_minutes 应透传给 storage，
    且 create_by 应为当前登录管理员用户名"""
    login(client, admin_user)
    api._user_storage.create_user.return_value = {**admin_user, 'id': 9, 'username': 'newbie'}
    resp = client.post('/api/users', json={
        'username': 'newbie',
        'password': 'pass',
        'role': 'user',
        'enabled': False,
        'display_name': '新人',
        'session_ttl_minutes': 30
    })
    assert resp.status_code == 201
    passed = api._user_storage.create_user.call_args[0][0]
    assert passed['username'] == 'newbie'
    assert passed['role'] == 'user'
    assert passed['enabled'] is False
    assert passed['display_name'] == '新人'
    assert passed['session_ttl_minutes'] == 30
    assert passed['create_by'] == 'admin'


def test_create_user_strips_username(client, api, admin_user, login):
    """用户名前后空格应被 strip 后透传"""
    login(client, admin_user)
    api._user_storage.create_user.return_value = {**admin_user, 'id': 9, 'username': 'newbie'}
    client.post('/api/users', json={'username': '  newbie  ', 'password': 'x'})
    assert api._user_storage.create_user.call_args[0][0]['username'] == 'newbie'


# ---------- 防自锁白名单：管理员可改自己密码 ----------

def test_admin_can_change_own_password(client, api, admin_user, login):
    """防自锁仅拦 enabled/role，不拦 password——管理员可改自己密码"""
    login(client, admin_user)  # admin_user id=1
    api._user_storage.update_user.return_value = True
    resp = client.put('/api/users/1', json={'password': 'newpass'})
    assert resp.status_code == 200
    api._user_storage.update_user.assert_called_once()


def test_admin_can_edit_own_display_name(client, api, admin_user, login):
    """防自锁不拦 display_name/remark 等非危险字段"""
    login(client, admin_user)
    api._user_storage.update_user.return_value = True
    resp = client.put('/api/users/1', json={'display_name': '新名字', 'remark': '备注'})
    assert resp.status_code == 200
    api._user_storage.update_user.assert_called_once()


def test_update_password_propagated_to_storage(client, api, admin_user, login):
    """更新密码时 password 字段透传给 storage"""
    login(client, admin_user)
    api._user_storage.update_user.return_value = True
    client.put('/api/users/2', json={'password': 'secret123'})
    args = api._user_storage.update_user.call_args[0]
    assert args[0] == 2
    assert args[1]['password'] == 'secret123'


# ---------- _to_dict 不泄露敏感字段（纯函数，不连库） ----------

def _build_user(**overrides):
    u = User()
    u.id = 1
    u.username = 'admin'
    u.password_hash = 'scrypt:secret-hash'
    u.display_name = '管理员'
    u.role = 'admin'
    u.enabled = 1
    u.session_ttl_minutes = 60
    u.del_flag = '1'
    u.remark = ''
    u.create_time = None
    u.update_time = None
    for k, v in overrides.items():
        setattr(u, k, v)
    return u


def test_to_dict_omits_sensitive_fields():
    """_to_dict 不得输出 password_hash / password / del_flag 等内部字段"""
    d = _to_dict(_build_user())
    assert 'password_hash' not in d
    assert 'password' not in d
    assert 'del_flag' not in d
    assert d['username'] == 'admin'
    assert d['enabled'] is True
    assert d['role'] == 'admin'
    assert d['session_ttl_minutes'] == 60


def test_to_dict_disabled_user_is_false():
    """enabled=0 → bool False"""
    d = _to_dict(_build_user(enabled=0))
    assert d['enabled'] is False


def test_to_dict_none_returns_none():
    assert _to_dict(None) is None


# ---------- 未登录 logout ----------

def test_unauthenticated_logout_401(client):
    """未登录调用 logout 应 401（受 before_request 保护）"""
    resp = client.post('/api/logout')
    assert resp.status_code == 401


# ---------- 用户列表 enabled 过滤参数透传 ----------

def test_get_users_enabled_filter_passed_to_storage(client, api, admin_user, login):
    """前端传 enabled=false（字符串）应透传给 storage（非空时），
    空 enabled 应转为 None（不过滤）"""
    login(client, admin_user)
    api._user_storage.get_users_with_pagination.return_value = ([], 0)
    client.get('/api/users?enabled=false')
    assert api._user_storage.get_users_with_pagination.call_args[1]['enabled'] == 'false'

    client.get('/api/users')
    assert api._user_storage.get_users_with_pagination.call_args[1]['enabled'] is None
