#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓组合和持仓关联数据存储层
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, CHAR
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event

from ..utils.config import get_db_url
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base


class PortfolioPosition(Base):
    __tablename__ = 'portfolio_position'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    portfolio_id = Column(BigInteger, nullable=False)
    position_id = Column(BigInteger, nullable=False)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)
    remark = Column(String(500))


class PortfolioPositionStorage:
    _engine = None
    _session_factory = None

    def __init__(self):
        if PortfolioPositionStorage._engine is None:
            PortfolioPositionStorage._engine = self._get_engine()
        if PortfolioPositionStorage._session_factory is None:
            PortfolioPositionStorage._session_factory = sessionmaker(bind=PortfolioPositionStorage._engine)
        self.Session = PortfolioPositionStorage._session_factory
        self.session = self.Session()

    @classmethod
    def _get_engine(cls):
        if cls._engine is None:
            db_url = get_db_url()
            cls._engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False
            )

            @event.listens_for(cls._engine, 'connect')
            def set_timezone_on_connect(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET time_zone = '+08:00'")
                cursor.execute("SET NAMES utf8mb4")
                cursor.close()

        return cls._engine

    def get_session(self):
        """获取数据库会话"""
        return PortfolioPositionStorage._session_factory()

    def get_portfolio_positions(self, portfolio_id: int) -> List[Dict]:
        """获取组合下的所有持仓"""
        session = self.get_session()
        try:
            relations = session.query(PortfolioPosition).filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.del_flag == '1'
            ).all()
            
            result = []
            for relation in relations:
                result.append({
                    'id': relation.id,
                    'portfolio_id': relation.portfolio_id,
                    'position_id': relation.position_id,
                    'remark': relation.remark,
                    'create_time': str(relation.create_time) if relation.create_time else None,
                    'update_time': str(relation.update_time) if relation.update_time else None
                })
            
            return result
        finally:
            session.close()

    def get_position_portfolios(self, position_id: int) -> List[Dict]:
        """获取持仓所属的所有组合"""
        session = self.get_session()
        try:
            relations = session.query(PortfolioPosition).filter(
                PortfolioPosition.position_id == position_id,
                PortfolioPosition.del_flag == '1'
            ).all()
            
            result = []
            for relation in relations:
                result.append({
                    'id': relation.id,
                    'portfolio_id': relation.portfolio_id,
                    'position_id': relation.position_id,
                    'remark': relation.remark,
                    'create_time': str(relation.create_time) if relation.create_time else None,
                    'update_time': str(relation.update_time) if relation.update_time else None
                })
            
            return result
        finally:
            session.close()

    def create_portfolio_position(self, portfolio_id: int, position_id: int, remark: str = '') -> int:
        """创建组合和持仓的关联"""
        session = self.get_session()
        try:
            # 检查是否已存在关联
            existing = session.query(PortfolioPosition).filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.position_id == position_id
            ).first()
            
            if existing:
                # 如果已存在但被删除，恢复它
                if existing.del_flag == '0':
                    existing.del_flag = '1'
                    existing.update_time = get_beijing_now()
                    session.commit()
                    return existing.id
                else:
                    # 已存在且有效，返回ID
                    return existing.id
            
            # 创建新关联
            relation = PortfolioPosition(
                portfolio_id=portfolio_id,
                position_id=position_id,
                del_flag='1',
                create_by='system',
                create_time=get_beijing_now(),
                update_by='system',
                update_time=get_beijing_now(),
                remark=remark
            )
            
            session.add(relation)
            session.commit()
            
            return relation.id
        except Exception as e:
            session.rollback()
            logger.error(f"创建组合持仓关联失败: {e}")
            raise e
        finally:
            session.close()

    def delete_portfolio_position(self, relation_id: int) -> bool:
        """删除组合和持仓的关联（逻辑删除）"""
        session = self.get_session()
        try:
            relation = session.query(PortfolioPosition).filter(
                PortfolioPosition.id == relation_id,
                PortfolioPosition.del_flag == '1'
            ).first()
            
            if not relation:
                return False
            
            relation.del_flag = '0'
            relation.update_time = get_beijing_now()
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除组合持仓关联失败: {e}")
            raise e
        finally:
            session.close()

    def delete_portfolio_positions_by_portfolio(self, portfolio_id: int) -> int:
        """删除组合下的所有持仓关联（逻辑删除）"""
        session = self.get_session()
        try:
            relations = session.query(PortfolioPosition).filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.del_flag == '1'
            ).all()
            
            count = 0
            for relation in relations:
                relation.del_flag = '0'
                relation.update_time = get_beijing_now()
                count += 1
            
            session.commit()
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"删除组合持仓关联失败: {e}")
            raise e
        finally:
            session.close()

    def close(self):
        if self.session:
            self.session.close()