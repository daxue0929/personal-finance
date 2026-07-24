#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓数据存储层
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR, func, and_, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event

from ..utils.config import get_db_url
from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


class Position(Base):
    __tablename__ = 'position'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    fund_name = Column(String(64))
    shares = Column(DECIMAL(15, 4), default=0.0000)
    cost_price = Column(DECIMAL(7, 4), default=0.0000)
    current_price = Column(DECIMAL(7, 4), default=0.0000)
    current_value = Column(DECIMAL(15, 2), default=0.00)
    cost_amount = Column(DECIMAL(15, 2), default=0.00)
    profit_loss = Column(DECIMAL(15, 2), default=0.00)
    profit_loss_rate = Column(DECIMAL(6, 2), default=0.00)
    buy_date = Column(Date)
    index_code = Column(String(10))
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)
    remark = Column(String(500))


class PositionStorage(StorageBase):
    """持仓数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_positions_with_pagination(self, fund_code=None, fund_name=None, page=1, page_size=10):
        """
        获取持仓列表（支持搜索和分页）
        :param fund_code: 基金代码（模糊搜索）
        :param fund_name: 基金名称（模糊搜索）
        :param page: 页码
        :param page_size: 每页条数
        :return: (数据列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(Position).filter(Position.del_flag == '1')
            
            # 添加搜索条件
            if fund_code:
                query = query.filter(Position.fund_code.like(f'%{fund_code}%'))
            if fund_name:
                query = query.filter(Position.fund_name.like(f'%{fund_name}%'))
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            positions = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for position in positions:
                result.append({
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
                    'index_code': position.index_code,
                    'remark': position.remark,
                    'create_time': str(position.create_time) if position.create_time else None,
                    'update_time': str(position.update_time) if position.update_time else None
                })
            
            return result, total
        finally:
            session.close()

    def get_position_by_id(self, position_id: int) -> Optional[Dict]:
        """根据ID获取持仓"""
        session = self.get_session()
        try:
            position = session.query(Position).filter(
                Position.id == position_id,
                Position.del_flag == '1'
            ).first()
            
            if position:
                return {
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
                    'index_code': position.index_code,
                    'remark': position.remark,
                    'create_time': str(position.create_time) if position.create_time else None,
                    'update_time': str(position.update_time) if position.update_time else None
                }
            return None
        finally:
            session.close()

    def create_position(self, data: Dict) -> int:
        """创建持仓"""
        session = self.get_session()
        try:
            # 计算相关字段
            shares = float(data.get('shares', 0))
            cost_price = float(data.get('cost_price', 0))
            current_price = float(data.get('current_price', 0))
            
            cost_amount = shares * cost_price
            current_value = shares * current_price
            profit_loss = current_value - cost_amount
            profit_loss_rate = (profit_loss / cost_amount * 100) if cost_amount > 0 else 0
            
            position = Position(
                fund_code=data.get('fund_code'),
                fund_name=data.get('fund_name', ''),
                shares=shares,
                cost_price=cost_price,
                current_price=current_price,
                current_value=current_value,
                cost_amount=cost_amount,
                profit_loss=profit_loss,
                profit_loss_rate=profit_loss_rate,
                buy_date=datetime.strptime(data.get('buy_date'), '%Y-%m-%d').date() if data.get('buy_date') else None,
                index_code=data.get('index_code'),
                del_flag='1',
                create_by=data.get('create_by', 'system'),
                create_time=get_beijing_now(),
                update_by=data.get('update_by', 'system'),
                update_time=get_beijing_now(),
                remark=data.get('remark', '')
            )
            
            session.add(position)
            session.commit()
            
            return position.id
        except Exception as e:
            session.rollback()
            logger.error(f"创建持仓失败: {e}")
            raise e
        finally:
            session.close()

    def update_position(self, position_id: int, data: Dict) -> bool:
        """更新持仓"""
        session = self.get_session()
        try:
            position = session.query(Position).filter(
                Position.id == position_id,
                Position.del_flag == '1'
            ).first()
            
            if not position:
                return False
            
            # 更新字段
            for key, value in data.items():
                if hasattr(position, key) and key not in ['id', 'del_flag']:
                    setattr(position, key, value)
            
            # 重新计算相关字段
            if 'shares' in data or 'cost_price' in data or 'current_price' in data:
                shares = float(position.shares) if position.shares else 0
                cost_price = float(position.cost_price) if position.cost_price else 0
                current_price = float(position.current_price) if position.current_price else 0
                
                position.cost_amount = shares * cost_price
                position.current_value = shares * current_price
                position.profit_loss = position.current_value - position.cost_amount
                position.profit_loss_rate = (position.profit_loss / position.cost_amount * 100) if position.cost_amount > 0 else 0
            
            position.update_time = get_beijing_now()
            position.update_by = data.get('update_by', 'system')
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新持仓失败: {e}")
            raise e
        finally:
            session.close()

    def delete_position(self, position_id: int) -> bool:
        """删除持仓（逻辑删除）"""
        session = self.get_session()
        try:
            position = session.query(Position).filter(
                Position.id == position_id,
                Position.del_flag == '1'
            ).first()
            
            if not position:
                return False
            
            position.del_flag = '0'
            position.update_time = get_beijing_now()
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除持仓失败: {e}")
            raise e
        finally:
            session.close()

    def get_position_by_fund_code(self, fund_code: str) -> Optional[Dict]:
        """
        根据基金代码获取持仓记录
        :param fund_code: 基金代码
        :return: 持仓信息，不存在返回None
        """
        session = self.get_session()
        try:
            position = session.query(Position).filter(
                Position.fund_code == fund_code,
                Position.del_flag == '1'
            ).first()
            
            if position:
                return {
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
                    'index_code': position.index_code,
                    'remark': position.remark
                }
            return None
        finally:
            session.close()

