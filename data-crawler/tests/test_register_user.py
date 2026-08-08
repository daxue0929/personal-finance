"""
register_user_via_invite 任务单元测试（PRD multi-user AC-2 T3.5）

TDD：4 case 覆盖邀请码注册 user 的事务逻辑。
mock UserStorage/InviteCodeStorage 类，验证任务行为。
"""
from unittest.mock import MagicMock, patch


# ==================== 测试辅助 ====================

def _make_user_mock():
    return MagicMock()


def _make_invite_mock():
    return MagicMock()


def _call_register(user_instance, invite_instance, **kwargs):
    """在 patch 上下文内调 register_user_via_invite(...)，避免 mock 在 with 块外失效。"""
    import sys
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith('app.task.register_user_via_invite'):
            del sys.modules[mod_name]
    with patch('app.storage.user_storage.UserStorage', return_value=user_instance), \
         patch('app.storage.invite_code_storage.InviteCodeStorage', return_value=invite_instance):
        from app.task import register_user_via_invite as task
        return task.register_user_via_invite(**kwargs)


# ==================== 1. 有效邀请码 ====================

def test_register_success_with_valid_invite():
    """有效邀请码 → 创 user + 标记邀请码已用"""
    user_mock = _make_user_mock()
    invite_mock = _make_invite_mock()
    invite_mock.validate.return_value = {
        'id': 5, 'code': 'ABCD1234', 'created_by': 1, 'expires_at': '2099-12-31',
        'used_at': None, 'used_by': None
    }
    user_mock.create_user.return_value = {
        'id': 10, 'username': 'alice', 'role': 'user', 'enabled': True,
    }

    result = _call_register(
        user_mock, invite_mock,
        username='alice', password='pw', display_name='Alice', invite_code='ABCD1234'
    )

    invite_mock.validate.assert_called_once_with('ABCD1234')
    user_mock.create_user.assert_called_once()
    # create_user 被传一个 dict（position arg），从 args[0] 取
    call_data = user_mock.create_user.call_args.args[0]
    assert call_data['username'] == 'alice'
    assert call_data['password'] == 'pw'
    invite_mock.mark_used.assert_called_once_with(invite_id=5, user_id=10)
    assert result['username'] == 'alice'
    assert result['id'] == 10


# ==================== 2. 无效邀请码 ====================

def test_register_fails_with_invalid_invite():
    """无效邀请码（不存在/过期/已用）→ 抛 ValueError，不创建 user"""
    user_mock = _make_user_mock()
    invite_mock = _make_invite_mock()
    invite_mock.validate.return_value = None

    try:
        _call_register(
            user_mock, invite_mock,
            username='bob', password='pw', display_name='', invite_code='INVALID'
        )
    except ValueError as e:
        assert '邀请码' in str(e)
    else:
        raise AssertionError('应抛 ValueError')

    user_mock.create_user.assert_not_called()
    invite_mock.mark_used.assert_not_called()


# ==================== 3. 用户名已存在 ====================

def test_register_fails_when_username_exists():
    """用户名已存在 → 创 user 抛 ValueError 透传，不 mark_used"""
    user_mock = _make_user_mock()
    invite_mock = _make_invite_mock()
    invite_mock.validate.return_value = {
        'id': 6, 'code': 'EFGH5678', 'created_by': 1
    }
    user_mock.create_user.side_effect = ValueError('用户名已存在')

    try:
        _call_register(
            user_mock, invite_mock,
            username='taken', password='pw', display_name='', invite_code='EFGH5678'
        )
    except ValueError as e:
        assert '已存在' in str(e)
    else:
        raise AssertionError('应透传 ValueError')

    invite_mock.mark_used.assert_not_called()


# ==================== 4. mark_used 失败但 user 已创建 ====================

def test_register_succeeds_even_if_mark_used_fails():
    """user 创建成功但 mark_used 失败 → 仍返回 user（已落库，不回滚）"""
    user_mock = _make_user_mock()
    invite_mock = _make_invite_mock()
    invite_mock.validate.return_value = {
        'id': 7, 'code': 'IJKL9012', 'created_by': 1
    }
    user_mock.create_user.return_value = {
        'id': 11, 'username': 'charlie', 'role': 'user', 'enabled': True,
    }
    invite_mock.mark_used.return_value = False

    result = _call_register(
        user_mock, invite_mock,
        username='charlie', password='pw', display_name='', invite_code='IJKL9012'
    )

    assert result['username'] == 'charlie'
    assert result['id'] == 11
    invite_mock.mark_used.assert_called_once()
