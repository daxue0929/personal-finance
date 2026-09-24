"""
pytest 公共夹具

测试通过 mock UserStorage 避免连接真实数据库（项目 .env 指向生产库，
绝不在测试中触碰）。仅验证鉴权/登录/用户管理的 HTTP 层与业务逻辑。

multi-user 扩展：
- 14 个业务 storage 的 opt-in mock fixture（business_storages_mock）— 测试按需 opt-in
- 字典构造器：_make_buyer / _make_portfolio / _make_invite / _make_position
- admin 切换 user 视角 fixture（impersonating_admin）

mock 策略沿用项目既有 per-file 模式（test_index_api / test_index_basic_api /
test_task_execution_tracking 各自定义 store = MagicMock()），不强制 autouse，
避免对现有测试产生隐式副作用。新测试按需显式 request `business_storages_mock`。
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


def _make_buyer(**overrides):
    """构造基金买入记录字典。必传 _id + fund_code + user_id。"""
    base = {
        'id': 1,
        'fund_code': '000001',
        'fund_name': '测试基金',
        'time': '2026-08-01',
        'amt': 100.0,
        'type': '1',
        'policy': '',
        'del_flag': '1',
        'buy_status': 'PENDING',
        'shares': None,
        'remark': '',
        'user_id': 1,
        'create_time': None,
        'update_time': None,
    }
    base.update(overrides)
    return base


def _make_portfolio(**overrides):
    """构造持仓组合字典。必传 _id + user_id。"""
    base = {
        'id': 1,
        'name': '默认组合',
        'description': '',
        'total_value': 0.0,
        'total_cost': 0.0,
        'total_profit_loss': 0.0,
        'del_flag': '1',
        'user_id': 1,
        'create_time': None,
        'update_time': None,
        'remark': '',
    }
    base.update(overrides)
    return base


def _make_invite(**overrides):
    """构造邀请码字典。必传 _id + code + created_by。"""
    base = {
        'id': 1,
        'code': 'ABCD1234',
        'created_by': 1,
        'expires_at': '2099-12-31 23:59:59',
        'used_at': None,
        'used_by': None,
        'del_flag': '1',
        'create_time': None,
        'update_time': None,
    }
    base.update(overrides)
    return base


def _make_position(**overrides):
    """构造持仓字典。必传 _id + fund_code + user_id。"""
    base = {
        'id': 1,
        'fund_code': '000001',
        'fund_name': '测试基金',
        'shares': 0.0,
        'cost_price': 0.0,
        'current_price': 0.0,
        'current_value': 0.0,
        'cost_amount': 0.0,
        'profit_loss': 0.0,
        'profit_loss_rate': 0.0,
        'buy_date': None,
        'del_flag': '1',
        'user_id': 1,
        'create_time': None,
        'update_time': None,
        'remark': '',
    }
    base.update(overrides)
    return base


def paddleocr_installed():
    """paddleocr 是否已安装（真实 OCR 集成测试的前置条件）"""
    try:
        import paddleocr  # noqa: F401
        return True
    except ImportError:
        return False


# 真实 OCR 集成测试统一 skip 守卫：未安装 paddleocr 时跳过并给出安装指引
requires_ocr = pytest.mark.skipif(
    not paddleocr_installed(),
    reason='paddleocr 未安装，跳过真实 OCR 测试；安装：pip install -r requirements-ocr.txt',
)


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
def business_storages_mock(api, client):
    """opt-in fixture: 替换 14 个业务 storage 为 MagicMock（沿用 per-file 模式，非 autouse）。

    显式 request 此 fixture 的测试可访问 `api._buyer_storage` 等属性并配置其 return_value。
    不 request 时，业务 storage 仍是真实实例（按现有项目惯例，仅 user_storage 必 mock）。
    """
    mocks = {
        '_buyer_storage': MagicMock(),
        '_seller_storage': MagicMock(),
        '_portfolio_storage': MagicMock(),
        '_position_storage': MagicMock(),
        '_portfolio_position_storage': MagicMock(),
        '_log_storage': MagicMock(),
        '_run_record_storage': MagicMock(),
        '_task_storage': MagicMock(),
        '_fund_storage': MagicMock(),
        '_nav_storage': MagicMock(),
        '_index_storage': MagicMock(),
        '_index_basic_storage': MagicMock(),
        '_position_snapshot_storage': MagicMock(),
        '_dip_plan_storage': MagicMock(),
    }
    for attr, mock in mocks.items():
        setattr(api, attr, mock)
    yield mocks
    # 不显式清理；client fixture 每次创建新 test_client，next test 重置


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


@pytest.fixture
def impersonating_admin(client, admin_user, normal_user, login):
    """admin 已登录且 session 注入 impersonate_user_id=normal_user.id。

    用于测试 admin 切换 user 视角场景。注意：当前 api_server.py 的 require_auth
    钩子尚未实现 impersonation 覆盖（见 Task 4），因此 GET /api/me 仍返 admin；
    切到 target_user 的行为将在 Task 4 完成后由 require_auth 钩子实现。
    """
    login(client, admin_user)
    # 直接通过 session_transaction 注入 impersonate_user_id
    with client.session_transaction() as sess:
        sess['impersonate_user_id'] = normal_user['id']
    return client
