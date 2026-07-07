#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户数据存储层

提供用户登录凭证与用户管理的持久化操作。遵循全库 Storage 约定：
- ORM 模型继承 Base，Storage 类继承 StorageBase（自动加日志）
- 软删除 del_flag='1'/'0'
- 时间用 get_beijing_now()
- 密码使用 werkzeug.security 哈希（scrypt），不可逆
"""

from typing import List, Dict, Any, Optional

from sqlalchemy import Column, BigInteger, String, Integer, DateTime, CHAR
from sqlalchemy.exc import IntegrityError

from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase

from werkzeug.security import generate_password_hash, check_password_hash


class User(Base):
    __tablename__ = 'user'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(64), default='')
    role = Column(String(20), default='user')          # admin / user
    enabled = Column(Integer, default=1)                # 1 启用 / 0 禁用
    session_ttl_minutes = Column(Integer, default=60)   # 登录态保持时长（分钟）
    del_flag = Column(CHAR(1), default='1')             # 1 正常 / 0 删除
    create_by = Column(String(64), default='')
    create_time = Column(DateTime)
    update_by = Column(String(64), default='')
    update_time = Column(DateTime)
    remark = Column(String(500))


def _to_dict(user: Optional[User]) -> Optional[Dict[str, Any]]:
    """将 User 实体转为对外字典（不含 password_hash、del_flag 等内部字段）"""
    if not user:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or '',
        'role': user.role or 'user',
        'enabled': bool(user.enabled),
        'session_ttl_minutes': user.session_ttl_minutes if user.session_ttl_minutes is not None else 60,
        'remark': user.remark or '',
        'create_time': str(user.create_time) if user.create_time else None,
        'update_time': str(user.update_time) if user.update_time else None
    }


class UserStorage(StorageBase):
    """用户数据存储层"""

    def __init__(self):
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """校验用户名密码，返回用户信息（仅启用且未删除的用户）"""
        session = self.get_session()
        try:
            user = session.query(User).filter(
                User.username == username,
                User.del_flag == '1',
                User.enabled == 1
            ).first()
            if not user:
                return None
            if not check_password_hash(user.password_hash, password):
                return None
            return _to_dict(user)
        except Exception as e:
            logger.error(f"校验用户 {username} 失败: {e}")
            return None
        finally:
            session.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取用户（含未启用，但排除已删除）"""
        session = self.get_session()
        try:
            user = session.query(User).filter(
                User.id == user_id,
                User.del_flag == '1'
            ).first()
            return _to_dict(user)
        except Exception as e:
            logger.error(f"获取用户 {user_id} 失败: {e}")
            return None
        finally:
            session.close()

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户（含未启用，但排除已删除）"""
        session = self.get_session()
        try:
            user = session.query(User).filter(
                User.username == username,
                User.del_flag == '1'
            ).first()
            return _to_dict(user)
        except Exception as e:
            logger.error(f"获取用户 {username} 失败: {e}")
            return None
        finally:
            session.close()

    def get_users_with_pagination(self, username=None, role=None, enabled=None,
                                  page=1, page_size=10):
        """获取用户列表（支持搜索、分页）"""
        session = self.get_session()
        try:
            query = session.query(User).filter(User.del_flag == '1')

            if username:
                query = query.filter(User.username.like(f'%{username}%'))
            if role:
                query = query.filter(User.role == role)
            if enabled is not None and enabled != '':
                # 前端 axios 序列化布尔值为 'true'/'false' 字符串
                query = query.filter(User.enabled == (1 if str(enabled).lower() in ('1', 'true') else 0))

            query = query.order_by(User.id.asc())
            total = query.count()
            users = query.offset((page - 1) * page_size).limit(page_size).all()
            return [_to_dict(u) for u in users], total
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return [], 0
        finally:
            session.close()

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户。用户名重复抛 ValueError；成功返回用户字典"""
        session = self.get_session()
        try:
            new_user = User(
                username=data['username'],
                password_hash=generate_password_hash(data['password']),
                display_name=data.get('display_name', ''),
                role=data.get('role', 'user'),
                enabled=1 if data.get('enabled', True) else 0,
                session_ttl_minutes=int(data.get('session_ttl_minutes', 60) or 60),
                del_flag='1',
                create_by=data.get('create_by', 'api'),
                create_time=get_beijing_now(),
                update_by=data.get('create_by', 'api'),
                update_time=get_beijing_now(),
                remark=data.get('remark', '')
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            logger.info(f"创建用户成功: {new_user.username} (id={new_user.id})")
            return _to_dict(new_user)
        except IntegrityError as e:
            session.rollback()
            logger.warning(f"创建用户失败（用户名已存在）: {data.get('username')}")
            raise ValueError('用户名已存在')
        except Exception as e:
            session.rollback()
            logger.error(f"创建用户失败: {e}")
            raise
        finally:
            session.close()

    def update_user(self, user_id: int, data: Dict[str, Any]) -> bool:
        """更新用户。password 留空则不修改。返回是否找到并更新"""
        session = self.get_session()
        try:
            user = session.query(User).filter(
                User.id == user_id,
                User.del_flag == '1'
            ).first()
            if not user:
                logger.warning(f"用户 {user_id} 不存在")
                return False

            if 'password' in data and data['password']:
                user.password_hash = generate_password_hash(data['password'])
            if 'display_name' in data:
                user.display_name = data['display_name']
            if 'role' in data:
                user.role = data['role']
            if 'enabled' in data and data['enabled'] is not None:
                user.enabled = 1 if data['enabled'] else 0
            if 'session_ttl_minutes' in data and data['session_ttl_minutes'] is not None:
                user.session_ttl_minutes = int(data['session_ttl_minutes'])
            if 'remark' in data:
                user.remark = data['remark']

            user.update_by = data.get('update_by', 'api')
            user.update_time = get_beijing_now()

            session.commit()
            logger.info(f"更新用户成功: {user_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新用户 {user_id} 失败: {e}")
            return False
        finally:
            session.close()

    def delete_user(self, user_id: int) -> bool:
        """软删除用户"""
        session = self.get_session()
        try:
            user = session.query(User).filter(
                User.id == user_id,
                User.del_flag == '1'
            ).first()
            if not user:
                logger.warning(f"用户 {user_id} 不存在")
                return False
            user.del_flag = '0'
            user.update_by = 'api'
            user.update_time = get_beijing_now()
            session.commit()
            logger.info(f"删除用户成功: {user_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除用户 {user_id} 失败: {e}")
            return False
        finally:
            session.close()
