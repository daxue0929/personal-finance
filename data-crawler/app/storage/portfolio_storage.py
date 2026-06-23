#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓组合数据存储层
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event

from ..utils.config import get_db_url
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base


class Portfolio(Base):
    __tablename__ = 'portfolio'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    description = Column(String(500))
    total_value = Column(DECIMAL(15, 2), default=0.00)
    total_cost = Column(DECIMAL(15, 2), default=0.00)
    total_profit_loss = Column(DECIMAL(15, 2), default=0.00)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)
    remark = Column(String(500))


class PortfolioStorage:
    _engine = None
    _session_factory = None

    def __init__(self):
        if PortfolioStorage._engine is None:
            PortfolioStorage._engine = self._get_engine()
        if PortfolioStorage._session_factory is None:
            PortfolioStorage._session_factory = sessionmaker(bind=PortfolioStorage._engine)
        self.Session = PortfolioStorage._session_factory
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
        return PortfolioStorage._session_factory()

    def get_portfolios_with_pagination(self, name=None, page=1, page_size=10):
        """
        获取持仓组合列表（支持搜索和分页）
        :param name: 组合名称（模糊搜索）
        :param page: 页码
        :param page_size: 每页条数
        :return: (数据列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(Portfolio).filter(Portfolio.del_flag == '1')
            
            # 添加搜索条件
            if name:
                query = query.filter(Portfolio.name.like(f'%{name}%'))
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            portfolios = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for portfolio in portfolios:
                result.append({
                    'id': portfolio.id,
                    'name': portfolio.name,
                    'description': portfolio.description,
                    'remark': portfolio.remark,
                    'create_time': str(portfolio.create_time) if portfolio.create_time else None,
                    'update_time': str(portfolio.update_time) if portfolio.update_time else None
                })
            
            return result, total
        finally:
            session.close()

    def get_portfolio_by_id(self, portfolio_id: int) -> Optional[Dict]:
        """根据ID获取持仓组合"""
        session = self.get_session()
        try:
            portfolio = session.query(Portfolio).filter(
                Portfolio.id == portfolio_id,
                Portfolio.del_flag == '1'
            ).first()
            
            if portfolio:
                return {
                    'id': portfolio.id,
                    'name': portfolio.name,
                    'description': portfolio.description,
                    'total_value': float(portfolio.total_value) if portfolio.total_value else 0.0,
                    'total_cost': float(portfolio.total_cost) if portfolio.total_cost else 0.0,
                    'total_profit_loss': float(portfolio.total_profit_loss) if portfolio.total_profit_loss else 0.0,
                    'remark': portfolio.remark,
                    'create_time': str(portfolio.create_time) if portfolio.create_time else None,
                    'update_time': str(portfolio.update_time) if portfolio.update_time else None
                }
            return None
        finally:
            session.close()

    def create_portfolio(self, data: Dict) -> int:
        """创建持仓组合"""
        session = self.get_session()
        try:
            portfolio = Portfolio(
                name=data.get('name'),
                description=data.get('description', ''),
                total_value=data.get('total_value', 0.0),
                total_cost=data.get('total_cost', 0.0),
                total_profit_loss=data.get('total_profit_loss', 0.0),
                del_flag='1',
                create_by=data.get('create_by', 'system'),
                create_time=get_beijing_now(),
                update_by=data.get('update_by', 'system'),
                update_time=get_beijing_now(),
                remark=data.get('remark', '')
            )
            
            session.add(portfolio)
            session.commit()
            
            return portfolio.id
        except Exception as e:
            session.rollback()
            logger.error(f"创建持仓组合失败: {e}")
            raise e
        finally:
            session.close()

    def update_portfolio(self, portfolio_id: int, data: Dict) -> bool:
        """更新持仓组合"""
        session = self.get_session()
        try:
            portfolio = session.query(Portfolio).filter(
                Portfolio.id == portfolio_id,
                Portfolio.del_flag == '1'
            ).first()
            
            if not portfolio:
                return False
            
            # 更新字段
            for key, value in data.items():
                if hasattr(portfolio, key) and key not in ['id', 'del_flag']:
                    setattr(portfolio, key, value)
            
            portfolio.update_time = get_beijing_now()
            portfolio.update_by = data.get('update_by', 'system')
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新持仓组合失败: {e}")
            raise e
        finally:
            session.close()

    def delete_portfolio(self, portfolio_id: int) -> bool:
        """删除持仓组合（逻辑删除）"""
        session = self.get_session()
        try:
            portfolio = session.query(Portfolio).filter(
                Portfolio.id == portfolio_id,
                Portfolio.del_flag == '1'
            ).first()
            
            if not portfolio:
                return False
            
            portfolio.del_flag = '0'
            portfolio.update_time = get_beijing_now()
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除持仓组合失败: {e}")
            raise e
        finally:
            session.close()

    def close(self):
        if self.session:
            self.session.close()