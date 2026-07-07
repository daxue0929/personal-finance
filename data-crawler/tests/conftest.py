"""
pytest 公共夹具

测试通过 mock UserStorage 避免连接真实数据库（项目 .env 指向生产库，
绝不在测试中触碰）。仅验证鉴权/登录/用户管理的 HTTP 层与业务逻辑。
"""
import os
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

# 在导入 app 之前注入环境变量（避免读取真实 .env 的生产配置）
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('MYSQL_HOST', '127.0.0.1')
os.environ.setdefault('SQL_ECHO', 'false')


def _make_user(**overrides):
    base = {
        'id': 1,
        'username': 'admin',
        'display_name': '管理员',
        'role': 'admin',
        'enabled': True,
        'session_ttl_minutes': 60,
        'del_flag': '1',
        'remark': '',
        'create_time': None,
        'update_time': None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def api():
    from app.web import api_server
    return api_server


@pytest.fixture
def client(api):
    """Flask 测试客户端，已注入 mock 用户存储"""
    api.app.config['TESTING'] = True
    api.app.config['SECRET_KEY'] = 'test-secret-key'
    api.app.permanent_session_lifetime = timedelta(minutes=60)
    store = MagicMock()
    api._user_storage = store
    with api.app.test_client() as c:
        yield c


@pytest.fixture
def admin_user():
    return _make_user(id=1, username='admin', role='admin')


@pytest.fixture
def normal_user():
    return _make_user(id=2, username='lily', display_name='小李', role='user')


@pytest.fixture
def login(api):
    """返回一个登录辅助函数：login(client, user) 完成登录并种下 cookie"""
    def _login(client, user):
        api._user_storage.verify_user.return_value = user
        api._user_storage.get_user_by_id.return_value = user
        resp = client.post('/api/login', json={
            'username': user['username'],
            'password': 'whatever'
        })
        assert resp.status_code == 200, resp.get_json()
        return resp
    return _login
