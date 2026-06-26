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
                    'remark': position.remark
                }
            return None
        finally:
            session.close()

    def update_position_by_buyer(self, position_id: int, new_shares: float, cost_price: float, buy_date: str, new_cost_amount: float, current_price: float = None) -> bool:
        """
        根据买入流水更新持仓数据（累加份额，重新计算成本价）
        :param position_id: 持仓ID
        :param new_shares: 新买入份额
        :param cost_price: 本次买入净值（成本价）
        :param buy_date: 本次买入日期
        :param new_cost_amount: 本次买入金额（直接从流水传入，避免浮点精度问题）
        :param current_price: 当前最新净值（可选，不传则使用数据库中已有值）
        :return: True/False
        """
        session = self.get_session()
        try:
            position = session.query(Position).filter(
                Position.id == position_id,
                Position.del_flag == '1'
            ).first()
            
            if not position:
                logger.warning(f"持仓记录 {position_id} 不存在")
                return False

            # 获取原有数据
            old_shares = float(position.shares) if position.shares else 0.0
            old_cost_amount = float(position.cost_amount) if position.cost_amount else 0.0
            
            # 累加份额
            total_shares = old_shares + new_shares
            
            # 计算加权平均成本价
            if total_shares > 0:
                weighted_cost_price = (old_cost_amount + new_cost_amount) / total_shares
            else:
                weighted_cost_price = cost_price

            # 更新持仓
            position.shares = total_shares
            position.cost_price = weighted_cost_price
            position.cost_amount = old_cost_amount + new_cost_amount
            
            # 更新买入日期
            from datetime import datetime
            position.buy_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
            
            # 更新当前净值（如果传入了最新净值）
            if current_price is not None and current_price > 0:
                position.current_price = current_price
            
            # 重新计算市值和盈亏（使用当前净值）
            current_price = float(position.current_price) if position.current_price else 0.0
            position.current_value = total_shares * current_price
            position.profit_loss = position.current_value - position.cost_amount
            if position.cost_amount > 0:
                position.profit_loss_rate = (position.profit_loss / position.cost_amount) * 100
            else:
                position.profit_loss_rate = 0

            position.update_by = 'system'
            position.update_time = get_beijing_now()

            session.commit()
            logger.info(
                f"更新持仓 {position_id}: 原份额 {old_shares} + 新份额 {new_shares} = 总份额 {total_shares}, "
                f"加权成本价 {weighted_cost_price:.4f}, 当前净值 {current_price:.4f}, 买入日期 {buy_date}"
            )
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新持仓 {position_id} 失败: {e}")
            return False
        finally:
            session.close()

