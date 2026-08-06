#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数基础信息数据存储层
配套功能：PRD "index-basic-table"
fetch_all_indexes_task 的元数据源。
"""
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import Column, String, SmallInteger, CHAR, DateTime

from ..utils.db import get_db_engine, get_db_session
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


class IndexBasic(Base):
    __tablename__ = 'index_basic'

    index_code = Column(String(6), primary_key=True)
    market = Column(String(4), nullable=False)
    index_name = Column(String(64), nullable=False)
    index_type = Column(String(20), nullable=False, default='宽基指数')
    enabled = Column(SmallInteger, nullable=False, default=1)
    del_flag = Column(CHAR(1), nullable=False, default='1')
    create_by = Column(String(64), nullable=False, default='')
    create_time = Column(DateTime, default=None)
    update_by = Column(String(64), nullable=False, default='')
    update_time = Column(DateTime, default=None)


# 字段白名单：create 和 update 都用这一份
_ALLOWED_FIELDS = frozenset({'market', 'index_name', 'index_type', 'enabled'})


class IndexBasicStorage(StorageBase):
    """指数基础信息数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    # ==================== 查询 ====================

    def get(self, index_code: str) -> Optional[IndexBasic]:
        """按主键查单条（不过滤 del_flag——软删行也可读，用于回滚/审计）"""
        session = self.get_session()
        try:
            return session.query(IndexBasic).filter(
                IndexBasic.index_code == index_code
            ).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 信息失败: {e}")
            return None
        finally:
            session.close()

    def list_all(self, include_disabled: bool = False, index_code: str = None,
                 index_type: str = None, page: int = 1, page_size: int = 20) -> tuple:
        """列出指数基础（含过滤 + 分页）。
        include_disabled=False：仅 enabled=1 AND del_flag='1'（前端默认）
        include_disabled=True：仅 del_flag='1'（包含已停用）
        index_code / index_type：精确过滤（None/空字符串 = 不过滤）
        page / page_size：分页（1-based，page_size 超过 100 截断为 100）

        Returns:
            (rows, total) tuple
        """
        session = self.get_session()
        try:
            q = session.query(IndexBasic).filter(IndexBasic.del_flag == '1')
            if not include_disabled:
                q = q.filter(IndexBasic.enabled == 1)
            if index_code:
                q = q.filter(IndexBasic.index_code == index_code)
            if index_type:
                q = q.filter(IndexBasic.index_type == index_type)

            total = q.count()
            page = max(1, page)
            page_size = max(1, min(100, page_size))
            rows = q.order_by(IndexBasic.index_code.asc()).offset(
                (page - 1) * page_size
            ).limit(page_size).all()
            return rows, total
        except Exception as e:
            logger.error(f"获取指数基础列表失败: {e}")
            return [], 0
        finally:
            session.close()

    def list_enabled(self) -> List[Tuple[str, str, str]]:
        """抓取任务用：返 (index_code, market, index_name) 三元组列表。
        过滤 enabled=1 AND del_flag='1'，按 code 升序。
        """
        session = self.get_session()
        try:
            rows = session.query(
                IndexBasic.index_code, IndexBasic.market, IndexBasic.index_name
            ).filter(
                IndexBasic.enabled == 1,
                IndexBasic.del_flag == '1'
            ).order_by(IndexBasic.index_code.asc()).all()
            return [(r[0], r[1], r[2]) for r in rows]
        except Exception as e:
            logger.error(f"获取启用指数列表失败: {e}")
            return []
        finally:
            session.close()

    # ==================== 校验 ====================

    @staticmethod
    def _validate_market(market: Any) -> None:
        if market not in ('sh', 'sz'):
            raise ValueError(f"market 必须是 'sh' 或 'sz', got {market!r}")

    @staticmethod
    def _validate_enabled(value: Any) -> None:
        """enabled 字段值域校验：仅接受 0/1（与 list_enabled 的 == 1 严格匹配保持一致）"""
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"enabled 必须为 0 或 1, got {value!r}")
        if v not in (0, 1):
            raise ValueError(f"enabled 必须为 0 或 1, got {v}")

    @staticmethod
    def _validate_index_code(index_code: Any) -> None:
        if not isinstance(index_code, str) or len(index_code) != 6 or not index_code.isdigit():
            raise ValueError(f"index_code 必须是 6 位数字字符串, got {index_code!r}")

    # ==================== 写入 ====================

    def create(self, data: Dict[str, Any]) -> bool:
        """新增指数元信息。
        校验：market ∈ {sh, sz}；index_code 6 位数字。
        字段白名单：market, index_name, index_type, enabled（index_code 来自入参主键）
        """
        index_code = data.get('index_code', '')
        self._validate_index_code(index_code)
        self._validate_market(data.get('market'))

        session = self.get_session()
        try:
            new_row = IndexBasic(
                index_code=index_code,
                market=data['market'],
                index_name=data.get('index_name', ''),
                index_type=data.get('index_type', '宽基指数'),
                enabled=int(data.get('enabled', 1)),
                del_flag='1',
                create_by=data.get('create_by', 'admin'),
                create_time=get_beijing_now(),
                update_by=data.get('create_by', 'admin'),
                update_time=get_beijing_now(),
            )
            session.add(new_row)
            session.commit()
            logger.info(f"新增指数基础 {index_code} 成功")
            return True
        except Exception as e:
            session.rollback()
            # 主键冲突包装为 ValueError，便于 API 层返 400
            from sqlalchemy.exc import IntegrityError
            if isinstance(e, IntegrityError):
                raise ValueError(f"指数代码 {index_code} 已存在") from e
            logger.error(f"新增指数基础失败: {e}")
            return False
        finally:
            session.close()

    def update(self, index_code: str, data: Dict[str, Any]) -> bool:
        """更新指数元信息。
        字段白名单：market, index_name, index_type, enabled。
        index_code 不可改（白名单不含 + 业务主键约定）。
        """
        session = self.get_session()
        try:
            row = session.query(IndexBasic).filter(
                IndexBasic.index_code == index_code,
                IndexBasic.del_flag == '1'
            ).first()
            if not row:
                logger.warning(f"指数基础 {index_code} 不存在或已删除")
                return False

            for field in _ALLOWED_FIELDS:
                if field in data:
                    # market / enabled 需校验值域（其他字段由 schema 约束）
                    if field == 'market':
                        self._validate_market(data[field])
                    elif field == 'enabled':
                        self._validate_enabled(data[field])
                    setattr(row, field, data[field])

            row.update_by = data.get('update_by', 'admin')
            row.update_time = get_beijing_now()
            session.commit()
            logger.info(f"更新指数基础 {index_code} 成功")
            return True
        except ValueError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"更新指数基础 {index_code} 失败: {e}")
            return False
        finally:
            session.close()

    # ==================== 软删 / 启停 ====================

    def soft_delete(self, index_code: str) -> bool:
        """软删：del_flag 置 '0'。index_info 历史不动。"""
        session = self.get_session()
        try:
            row = session.query(IndexBasic).filter(
                IndexBasic.index_code == index_code,
                IndexBasic.del_flag == '1'
            ).first()
            if not row:
                logger.warning(f"指数基础 {index_code} 不存在")
                return False
            row.del_flag = '0'
            row.update_by = 'admin'
            row.update_time = get_beijing_now()
            session.commit()
            logger.info(f"软删指数基础 {index_code} 成功")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"软删指数基础 {index_code} 失败: {e}")
            return False
        finally:
            session.close()

    def toggle_enabled(self, index_code: str, enabled: bool) -> bool:
        """启停：True→1，False→0。"""
        session = self.get_session()
        try:
            row = session.query(IndexBasic).filter(
                IndexBasic.index_code == index_code,
                IndexBasic.del_flag == '1'
            ).first()
            if not row:
                logger.warning(f"指数基础 {index_code} 不存在")
                return False
            row.enabled = 1 if enabled else 0
            row.update_by = 'admin'
            row.update_time = get_beijing_now()
            session.commit()
            logger.info(f"指数基础 {index_code} 启停为 {row.enabled}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"指数基础 {index_code} 启停失败: {e}")
            return False
        finally:
            session.close()
