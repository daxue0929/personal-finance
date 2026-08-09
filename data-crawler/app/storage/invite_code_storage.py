#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邀请码数据存储层（PRD multi-user AC-2）

提供 admin 生成邀请码 + user 注册时校验 + 标记已用的持久化操作。
遵循全库 Storage 约定：
- ORM 模型继承 Base，Storage 类继承 StorageBase（自动加日志）
- 软删除 del_flag='1'/'0'
- 时间用 get_beijing_now()
- 8 位 a-zA-Z0-9 邀请码（UNIQUE 约束兜底重试）
"""
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import Column, BigInteger, String, DateTime, CHAR
from sqlalchemy.exc import IntegrityError

from ..utils.db import get_db_engine, get_db_session
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now, BEIJING_TZ
from .base import Base, StorageBase


# 8 位 a-z A-Z 0-9 邀请码字符集（与全库 8 位约定一致）
_CODE_CHARS = string.ascii_letters + string.digits
_CODE_LENGTH = 8
_DEFAULT_TTL_DAYS = 7
_MAX_RETRY = 5


class InviteCode(Base):
    __tablename__ = 'invite_code'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(8), nullable=False, unique=True)
    created_by = Column(BigInteger, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by = Column(BigInteger, nullable=True)
    del_flag = Column(CHAR(1), default='1')
    create_time = Column(DateTime)
    update_time = Column(DateTime)


def _to_dict(invite: Optional[InviteCode]) -> Optional[Dict[str, Any]]:
    """InviteCode 实体 → 对外字典（不含 del_flag）"""
    if not invite:
        return None
    return {
        'id': invite.id,
        'code': invite.code,
        'created_by': invite.created_by,
        'expires_at': str(invite.expires_at) if invite.expires_at else None,
        'used_at': str(invite.used_at) if invite.used_at else None,
        'used_by': invite.used_by,
        'create_time': str(invite.create_time) if invite.create_time else None,
        'update_time': str(invite.update_time) if invite.update_time else None,
    }


class InviteCodeStorage(StorageBase):
    """邀请码数据存储层"""

    def __init__(self):
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        return self.Session()

    def _generate_code(self) -> str:
        """生成 8 位随机码（a-zA-Z0-9）"""
        return ''.join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LENGTH))

    def create(self, admin_id: int, ttl_days: int = _DEFAULT_TTL_DAYS) -> str:
        """admin 生成新邀请码，返回 code 字符串。

        UNIQUE 冲突时（极小概率）自动重试，最多重试 5 次。
        """
        session = self.get_session()
        try:
            for _ in range(_MAX_RETRY):
                code = self._generate_code()
                # 预查：UNIQUE 冲突则重试
                existing = session.query(InviteCode).filter(
                    InviteCode.code == code
                ).first()
                if existing:
                    continue

                now = get_beijing_now()
                expires_at = now + timedelta(days=ttl_days)

                new_invite = InviteCode(
                    code=code,
                    created_by=admin_id,
                    expires_at=expires_at,
                    used_at=None,
                    used_by=None,
                    del_flag='1',
                    create_time=now,
                    update_time=now,
                )
                try:
                    session.add(new_invite)
                    session.commit()
                    logger.info(f"生成邀请码成功: {code} (admin_id={admin_id}, ttl={ttl_days}d)")
                    return code
                except IntegrityError:
                    session.rollback()
                    continue

            raise RuntimeError("生成邀请码失败：UNIQUE 冲突重试 5 次后仍冲突")
        finally:
            session.close()

    def validate(self, code: str) -> Optional[Dict[str, Any]]:
        """校验邀请码：存在 + 未过期 + 未用 + 未软删。

        返回 invite 字典（已过期/已用/不存在返 None）。
        """
        session = self.get_session()
        try:
            invite = session.query(InviteCode).filter(
                InviteCode.code == code,
                InviteCode.del_flag == '1',
            ).first()
            if not invite:
                return None
            if invite.used_at is not None:
                logger.info(f"邀请码已被使用: {code}")
                return None
            now = get_beijing_now()
            if invite.expires_at:
                # MySQL DATETIME 列无 tzinfo，naive 视作北京时间（与 create() 写入语义一致）
                expires_at_aware = (
                    invite.expires_at
                    if invite.expires_at.tzinfo
                    else invite.expires_at.replace(tzinfo=BEIJING_TZ)
                )
                if expires_at_aware < now:
                    logger.info(f"邀请码已过期: {code} (expires_at={invite.expires_at})")
                    return None
            return _to_dict(invite)
        except Exception as e:
            logger.error(f"校验邀请码 {code} 失败: {e}")
            return None
        finally:
            session.close()

    def mark_used(self, invite_id: int, user_id: int) -> bool:
        """标记邀请码已用：置 used_at + used_by。"""
        session = self.get_session()
        try:
            invite = session.query(InviteCode).filter(
                InviteCode.id == invite_id,
                InviteCode.del_flag == '1',
            ).first()
            if not invite:
                logger.warning(f"邀请码 {invite_id} 不存在")
                return False
            invite.used_at = get_beijing_now()
            invite.used_by = user_id
            invite.update_time = get_beijing_now()
            session.commit()
            logger.info(f"邀请码已标记为已用: id={invite_id}, code={invite.code}, used_by={user_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"标记邀请码 {invite_id} 已用失败: {e}")
            return False
        finally:
            session.close()

    def list_by_admin(self, admin_id: int, include_used: bool = True,
                      include_expired: bool = True,
                      page: int = 1, page_size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        """admin 看自己生成的所有邀请码（分页）。

        include_used=False 时排除 used_at 非空；
        include_expired=False 时排除 expires_at < now。
        """
        session = self.get_session()
        try:
            query = session.query(InviteCode).filter(
                InviteCode.created_by == admin_id,
                InviteCode.del_flag == '1',
            )
            if not include_used:
                query = query.filter(InviteCode.used_at.is_(None))
            if not include_expired:
                # SQL 侧比较：DB 存的是 Beijing wall clock，剥 tz 传 naive 避免 MySQL server tz 干扰
                naive_now = get_beijing_now().replace(tzinfo=None)
                query = query.filter(InviteCode.expires_at >= naive_now)

            query = query.order_by(InviteCode.create_time.desc())
            total = query.count()
            invites = query.offset((page - 1) * page_size).limit(page_size).all()
            return [_to_dict(i) for i in invites], total
        except Exception as e:
            logger.error(f"获取 admin {admin_id} 邀请码列表失败: {e}")
            return [], 0
        finally:
            session.close()
