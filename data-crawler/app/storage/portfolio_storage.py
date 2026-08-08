#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓组合数据存储层
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.pool import QueuePool
from sqlalchemy import event, and_

from ..utils.config import get_db_url
from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


class Portfolio(Base):
    __tablename__ = 'portfolio'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, default=1, index=True, comment='所属 user（multi-user 隔离）')
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


class PortfolioStorage(StorageBase):
    """持仓组合数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_portfolios_with_pagination(self, user_id=None, name=None, page=1, page_size=10):
        """
        获取持仓组合列表（支持搜索和分页）
        :param user_id: 限定 user；None = 不过滤（admin 跨用户视角）
        :param name: 组合名称（模糊搜索）
        :param page: 页码
        :param page_size: 每页条数
        :return: (数据列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(Portfolio).filter(Portfolio.del_flag == '1')

            if user_id is not None:
                query = query.filter(Portfolio.user_id == user_id)

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

    def get_portfolio_with_positions(self, portfolio_id: int) -> Optional[Dict]:
        """
        获取持仓组合及其关联的所有持仓（使用JOIN查询优化性能）
        :param portfolio_id: 组合ID
        :return: 组合信息（包含positions列表）
        """
        session = self.get_session()
        try:
            from .position_storage import Position

            # 使用JOIN查询一次获取所有关联数据
            query = session.query(
                Portfolio,
                Position
            ).outerjoin(
                PortfolioPosition,
                and_(
                    PortfolioPosition.portfolio_id == Portfolio.id,
                    PortfolioPosition.del_flag == '1'
                )
            ).outerjoin(
                Position,
                and_(
                    Position.id == PortfolioPosition.position_id,
                    Position.del_flag == '1'
                )
            ).filter(
                Portfolio.id == portfolio_id,
                Portfolio.del_flag == '1'
            ).all()

            if not query:
                return None

            # 处理查询结果
            portfolio_info = None
            positions = []

            for row in query:
                portfolio, position = row

                if portfolio_info is None:
                    portfolio_info = {
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

                if position:
                    positions.append({
                        'id': position.id,
                        'fund_code': position.fund_code,
                        'fund_name': position.fund_name,
                        'shares': float(position.shares) if position.shares else 0.0,
                        'cost_price': float(position.cost_price) if position.cost_price else 0.0,
                        'current_price': float(position.current_price) if position.current_price else 0.0,
                        'current_value': float(position.current_value) if position.current_value else 0.0,
                        'cost_amount': float(position.cost_amount) if position.cost_amount else 0.0,
                        'profit_loss': float(position.profit_loss) if position.profit_loss else 0.0,
                        'profit_loss_rate': float(position.profit_loss_rate) if position.profit_loss_rate else 0.0,
                        'buy_date': str(position.buy_date) if position.buy_date else None,
                        'remark': position.remark,
                        'create_time': str(position.create_time) if position.create_time else None,
                        'update_time': str(position.update_time) if position.update_time else None
                    })

            # 使用SQL计算总市值和总成本，避免Python循环计算
            total_value = 0.0
            total_cost = 0.0

            if positions:
                # 批量查询计算统计数据
                position_ids = [p['id'] for p in positions]
                cost_prices = {pos['id']: pos['cost_price'] for pos in positions}
                shares = {pos['id']: pos['shares'] for pos in positions}
                current_values = {pos['id']: pos['current_value'] for pos in positions}

                for pos_id in position_ids:
                    total_value += float(current_values.get(pos_id, 0))
                    total_cost += float(shares.get(pos_id, 0)) * float(cost_prices.get(pos_id, 0))

            portfolio_info['positions'] = positions
            portfolio_info['total_value'] = total_value
            portfolio_info['total_cost'] = total_cost
            portfolio_info['total_profit_loss'] = total_value - total_cost

            return portfolio_info
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

