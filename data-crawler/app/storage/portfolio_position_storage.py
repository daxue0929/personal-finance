#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓组合和持仓关联数据存储层
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, CHAR, func, and_, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event

from ..utils.config import get_db_url
from ..utils.db import get_db_session, get_db_engine
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
    """持仓组合和持仓关联数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

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

    def get_portfolio_positions_with_stats(self, portfolio_id: int) -> tuple[List[Dict], float, float]:
        """
        获取组合下的所有持仓及其统计数据（使用JOIN查询优化）
        :param portfolio_id: 组合ID
        :return: (持仓列表, 总市值, 总成本)
        """
        session = self.get_session()
        try:
            from .position_storage import Position

            # 使用JOIN查询一次获取所有关联数据
            query = session.query(
                PortfolioPosition,
                Position
            ).join(
                Position,
                Position.id == PortfolioPosition.position_id,
                isouter=True
            ).filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.del_flag == '1',
                Position.del_flag == '1'
            ).all()

            positions = []
            total_value = 0.0
            total_cost = 0.0

            for relation, position in query:
                if position:
                    pos_data = {
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
                    positions.append(pos_data)

                    # 累加统计数据
                    total_value += float(position.current_value) if position.current_value else 0.0
                    total_cost += float(position.shares) * float(position.cost_price) if position.shares and position.cost_price else 0.0

            return positions, total_value, total_cost
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