#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邀请码注册 user 任务（PRD multi-user AC-2）

事务语义：
- 邀请码无效 → 抛 ValueError，不创建 user
- user 创建失败（如用户名已存在）→ 透传，不 mark_used
- user 创建成功但 mark_used 失败 → 仍返回 user（user 已落库是关键事实）
  这种情况下邀请码仍标为未用，admin 可清理；不影响用户登录。
"""
from typing import Dict, Any

from ..utils.logger import logger


def register_user_via_invite(*, username: str, password: str,
                             display_name: str, invite_code: str) -> Dict[str, Any]:
    """通过邀请码注册新 user。

    Returns:
        新 user 字典（id / username / role / enabled / ...）

    Raises:
        ValueError: 邀请码无效（不存在/过期/已用）
        ValueError: 用户名已存在（从 user_storage.create_user 透传）
    """
    # 函数内 import：确保 patch Storage 类时能被正确拦截（模块级 from import
    # 绑定的是 import 时的类引用，patch 修改模块属性不更新已绑定的局部名）
    from ..storage.user_storage import UserStorage
    from ..storage.invite_code_storage import InviteCodeStorage

    invite_storage = InviteCodeStorage()
    user_storage = UserStorage()

    # 1. 校验邀请码
    invite = invite_storage.validate(invite_code)
    if not invite:
        logger.warning(f"注册失败：邀请码无效或已用 invite_code={invite_code}")
        raise ValueError("邀请码无效、已过期或已被使用")

    # 2. 创建 user
    new_user = user_storage.create_user({
        'username': username,
        'password': password,
        'display_name': display_name,
        'role': 'user',
        'enabled': True,
        'create_by': f'invite:{invite["created_by"]}',
    })

    # 3. 标记邀请码已用（失败不回滚 user）
    try:
        ok = invite_storage.mark_used(invite_id=invite['id'], user_id=new_user['id'])
        if not ok:
            logger.warning(
                f"标记邀请码已用失败但 user 已创建: invite_id={invite['id']}, user_id={new_user['id']}"
            )
    except Exception as e:
        logger.error(f"标记邀请码已用异常: {e}")

    logger.info(f"邀请码注册成功: user_id={new_user['id']}, username={username}")
    return new_user
