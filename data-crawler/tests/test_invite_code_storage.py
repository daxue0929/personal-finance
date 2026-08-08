"""
InviteCodeStorage 单元测试（PRD multi-user AC-2 T3.1）

TDD：5 case 覆盖 create / validate / mark_used / list_by_admin。
mock 整个 session（不连真实 DB），验证 storage 行为正确。
"""
import string
from datetime import datetime
from unittest.mock import MagicMock


# ==================== 测试辅助 ====================

def _make_invite_row(**overrides):
    """构造模拟 InviteCode ORM 行。

    expires_at 默认用 timezone-aware（北京时区），匹配 get_beijing_now()。
    生产 MySQL DATETIME 列读取是 naive，但对比逻辑只关心时间值。
    """
    from datetime import timezone, timedelta as _td
    beijing = timezone(_td(hours=8))
    defaults = {
        'id': 1,
        'code': 'ABCD1234',
        'created_by': 1,
        'expires_at': datetime(2099, 12, 31, 23, 59, 59, tzinfo=beijing),
        'used_at': None,
        'used_by': None,
        'del_flag': '1',
        'create_time': datetime(2026, 8, 1, 0, 0, 0, tzinfo=beijing),
        'update_time': datetime(2026, 8, 1, 0, 0, 0, tzinfo=beijing),
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_storage_with_mock_session():
    """创建 InviteCodeStorage 实例，Session 替换为 MagicMock。"""
    from app.storage.invite_code_storage import InviteCodeStorage
    storage = InviteCodeStorage()
    storage.Session = MagicMock()
    mock_session = MagicMock()
    storage.Session.return_value = mock_session
    return storage, mock_session


# ==================== 1. create 生成 8 位码 ====================

def test_create_generates_8_char_code():
    """create 应生成 8 位 a-zA-Z0-9 字符串"""
    storage, mock_session = _make_storage_with_mock_session()
    # 第一次 add().code 检查：8 位
    # mock execute 返 row 但 query 返 None（无 UNIQUE 冲突）
    mock_session.query.return_value.filter.return_value.first.return_value = None

    code = storage.create(admin_id=1, ttl_days=7)
    assert len(code) == 8
    assert all(c in string.ascii_letters + string.digits for c in code)
    # 应调 session.add + session.commit
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_create_retries_on_unique_conflict():
    """UNIQUE 冲突时（已有同 code）应重试生成新码"""
    storage, mock_session = _make_storage_with_mock_session()
    # 第一次查冲突（生成第一个码）→ 返一个已存在的行；第二次查 → 返 None
    first_existing = _make_invite_row(code='CONFLICT1')
    mock_session.query.return_value.filter.return_value.first.side_effect = [first_existing, None]

    code = storage.create(admin_id=1, ttl_days=7)
    # 应重试，最终 add 的是第二个码
    added_row = mock_session.add.call_args.args[0]
    assert added_row.code == code
    # query 被调 ≥ 2 次
    assert mock_session.query.call_count >= 2


# ==================== 2. validate：过期/已用/软删 ====================

def test_validate_returns_dict_for_valid_code():
    """有效码（未过期 + 未用 + del_flag='1'）返 dict"""
    storage, mock_session = _make_storage_with_mock_session()
    valid_row = _make_invite_row(code='VALID123', used_at=None, del_flag='1')
    mock_session.query.return_value.filter.return_value.first.return_value = valid_row

    result = storage.validate('VALID123')
    assert result is not None
    assert result['code'] == 'VALID123'


def test_validate_expired_returns_none():
    """已过期的码应返 None"""
    from datetime import timezone, timedelta as _td
    storage, mock_session = _make_storage_with_mock_session()
    expired_row = _make_invite_row(
        code='EXPIRED1',
        expires_at=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone(_td(hours=8)))
    )
    mock_session.query.return_value.filter.return_value.first.return_value = expired_row

    result = storage.validate('EXPIRED1')
    assert result is None


def test_validate_used_returns_none():
    """已使用的码应返 None（used_at 非空）"""
    storage, mock_session = _make_storage_with_mock_session()
    used_row = _make_invite_row(
        code='USED0001',
        used_at=datetime(2026, 8, 1, 0, 0, 0),
        used_by=2
    )
    mock_session.query.return_value.filter.return_value.first.return_value = used_row

    result = storage.validate('USED0001')
    assert result is None


def test_validate_not_found_returns_none():
    """不存在的码应返 None"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    result = storage.validate('NOSUCH99')
    assert result is None


# ==================== 3. mark_used 置 used_at + used_by ====================

def test_mark_used_sets_timestamp_and_user():
    """mark_used 应置 used_at + used_by，返回 True"""
    storage, mock_session = _make_storage_with_mock_session()
    invite_row = _make_invite_row(id=5, code='TOUSE001', used_at=None, used_by=None)
    mock_session.query.return_value.filter.return_value.first.return_value = invite_row

    result = storage.mark_used(invite_id=5, user_id=2)
    assert result is True
    assert invite_row.used_at is not None
    assert invite_row.used_by == 2
    mock_session.commit.assert_called_once()


def test_mark_used_not_found_returns_false():
    """invite_id 不存在应返 False"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    result = storage.mark_used(invite_id=999, user_id=2)
    assert result is False


# ==================== 4. list_by_admin 过滤 ====================

def _filter_column_names(mock_query):
    """提取 query.filter() 所有调用的列名（来自 BinaryExpression.left.key）。"""
    names = []
    for call in mock_query.filter.call_args_list:
        for arg in call.args:
            # SQLAlchemy BinaryExpression 有 .left.key
            if hasattr(arg, 'left') and hasattr(arg.left, 'key'):
                names.append(arg.left.key)
            # 也支持单 col 形式（col.desc()、col.is_(None)）
            elif hasattr(arg, 'key'):
                names.append(arg.key)
            # ColumnElement（如 func.count()）走 .element
            elif hasattr(arg, 'element') and hasattr(arg.element, 'key'):
                names.append(arg.element.key)
    return names


def test_list_by_admin_filters_by_created_by():
    """list_by_admin 应只返 created_by=admin_id 的码"""
    storage, mock_session = _make_storage_with_mock_session()
    # query 返 [admin1_code, admin1_code2]
    rows = [
        _make_invite_row(id=1, code='ADMIN1A', created_by=1),
        _make_invite_row(id=2, code='ADMIN1B', created_by=1),
    ]
    # query chain: query().filter().orderby().offset().limit().all()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = rows
    mock_query.count.return_value = 2
    mock_session.query.return_value = mock_query

    result, total = storage.list_by_admin(admin_id=1)
    assert total == 2
    assert len(result) == 2
    col_names = _filter_column_names(mock_query)
    assert 'created_by' in col_names, f'缺少 created_by 过滤, 实际: {col_names}'
    assert 'del_flag' in col_names, f'缺少 del_flag 过滤, 实际: {col_names}'


def test_list_by_admin_excludes_used_when_flag_false():
    """include_used=False 时应过滤 used_at IS NOT NULL"""
    storage, mock_session = _make_storage_with_mock_session()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_query.count.return_value = 0
    mock_session.query.return_value = mock_query

    storage.list_by_admin(admin_id=1, include_used=False)
    col_names = _filter_column_names(mock_query)
    assert 'used_at' in col_names, f'include_used=False 时应过滤 used_at, 实际: {col_names}'
