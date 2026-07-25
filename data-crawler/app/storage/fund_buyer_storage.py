#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金买入流水数据存储层
"""

from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event

from ..utils.config import get_db_url
from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


def compute_buyer_shares(amt, nav):
    """纯计算：买入份额 = 金额 / 净值，四舍五入保留 4 位。nav<=0 返回 None。

    供 calculate_buyer_shares_task 与买入补录接口共用，保证份额算法一致。
    """
    nav = float(nav)
    if nav <= 0:
        return None
    shares = Decimal(str(amt)) / Decimal(str(nav))
    return shares.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def _compute_buyer_accumulation(old_shares, old_cost_amount, buy_shares, buy_amt, current_price):
    """纯计算：按加权平均成本法计算买入后的持仓累加（不依赖数据库，便于单元测试）。

    与卖出侧 _compute_sell_reduction 对称。幂等性由调用方（PENDING 状态机 + 原子事务）保证，
    本函数只做计算，不做日期水位判断。

    :param old_shares: 原持仓份额
    :param old_cost_amount: 原成本金额
    :param buy_shares: 本次买入份额
    :param buy_amt: 本次买入金额（直接从流水传入，避免浮点精度问题）
    :param current_price: 当前最新净值（用于重算市值/盈亏）
    :return: dict
        - {'ok': True, 'new_total_shares', 'new_cost_amount', 'weighted_cost_price',
           'current_value', 'profit_loss', 'profit_loss_rate'}
        - new_total_shares 为 0 时 current_value/profit_loss/profit_loss_rate 强制归零
    """
    old_shares = float(old_shares)
    old_cost_amount = float(old_cost_amount)
    buy_shares = float(buy_shares)
    buy_amt = float(buy_amt)
    current_price = float(current_price)

    new_total_shares = old_shares + buy_shares
    new_cost_amount = round(old_cost_amount + buy_amt, 2)

    if new_total_shares == 0:
        return {
            'ok': True,
            'new_total_shares': 0,
            'new_cost_amount': 0,
            'weighted_cost_price': 0,
            'current_value': 0,
            'profit_loss': 0,
            'profit_loss_rate': 0,
        }

    weighted_cost_price = new_cost_amount / new_total_shares
    current_value = round(new_total_shares * current_price, 2)
    profit_loss = round(current_value - new_cost_amount, 2)
    profit_loss_rate = round(profit_loss / new_cost_amount * 100, 2) if new_cost_amount > 0 else 0
    return {
        'ok': True,
        'new_total_shares': new_total_shares,
        'new_cost_amount': new_cost_amount,
        'weighted_cost_price': weighted_cost_price,
        'current_value': current_value,
        'profit_loss': profit_loss,
        'profit_loss_rate': profit_loss_rate,
    }


class FundBuyer(Base):
    __tablename__ = 'fund_buyer'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    fund_name = Column(String(64), default='')
    time = Column(Date, nullable=False, default=datetime.now().date())
    amt = Column(DECIMAL(10, 2), default=0.00)
    type = Column(String(64), default='')
    policy = Column(String(500), default='')
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64), default='')
    create_time = Column(DateTime)
    update_by = Column(String(64), default='')
    update_time = Column(DateTime)
    remark = Column(String(500))
    buy_status = Column(String(20), default='PENDING')
    shares = Column(DECIMAL(15, 4), default=None)


class FundBuyerStorage(StorageBase):
    """基金买入流水数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_all_buyers(self) -> List[FundBuyer]:
        """获取所有买入记录"""
        session = self.get_session()
        try:
            return session.query(FundBuyer).filter(
                FundBuyer.del_flag == '1'
            ).order_by(FundBuyer.time.desc()).all()
        except Exception as e:
            logger.error(f"获取买入记录失败: {e}")
            return []
        finally:
            session.close()

    def get_buyer_by_id(self, buyer_id: int) -> Optional[FundBuyer]:
        """根据ID获取买入记录"""
        session = self.get_session()
        try:
            return session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取买入记录 {buyer_id} 失败: {e}")
            return None
        finally:
            session.close()

    def create_buyer(self, data: Dict[str, Any]) -> bool:
        """创建买入记录"""
        session = self.get_session()
        try:
            new_buyer = FundBuyer(
                fund_code=data.get('fund_code', ''),
                fund_name=data.get('fund_name', ''),
                time=datetime.strptime(data.get('time'), '%Y-%m-%d').date() if data.get('time') else datetime.now().date(),
                amt=data.get('amt', 0.0),
                type=data.get('type', ''),
                policy=data.get('policy', ''),
                buy_status=data.get('buy_status', 'PENDING'),
                remark=data.get('remark', ''),
                del_flag='1',
                create_by=data.get('create_by', 'api'),
                create_time=get_beijing_now(),
                update_by=data.get('create_by', 'api'),
                update_time=get_beijing_now()
            )
            session.add(new_buyer)
            session.commit()
            session.refresh(new_buyer)
            logger.info(f"创建买入记录成功: {new_buyer.id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"创建买入记录失败: {e}")
            return False
        finally:
            session.close()

    def update_buyer(self, buyer_id: int, data: Dict[str, Any]) -> bool:
        """更新买入记录"""
        session = self.get_session()
        try:
            buyer = session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
            
            if not buyer:
                logger.warning(f"买入记录 {buyer_id} 不存在")
                return False

            if 'fund_code' in data:
                buyer.fund_code = data['fund_code']
            if 'fund_name' in data:
                buyer.fund_name = data['fund_name']
            if 'time' in data:
                buyer.time = datetime.strptime(data['time'], '%Y-%m-%d').date()
            if 'amt' in data:
                buyer.amt = data['amt']
            if 'type' in data:
                buyer.type = data['type']
            if 'policy' in data:
                buyer.policy = data['policy']
            if 'buy_status' in data:
                buyer.buy_status = data['buy_status']
            if 'shares' in data:
                buyer.shares = data['shares']
            if 'remark' in data:
                buyer.remark = data['remark']

            buyer.update_by = data.get('update_by', 'api')
            buyer.update_time = get_beijing_now()

            session.commit()
            logger.info(f"更新买入记录成功: {buyer_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新买入记录失败: {e}")
            return False
        finally:
            session.close()

    def delete_buyer(self, buyer_id: int) -> bool:
        """删除买入记录（软删除）"""
        session = self.get_session()
        try:
            buyer = session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
            
            if not buyer:
                logger.warning(f"买入记录 {buyer_id} 不存在")
                return False

            buyer.del_flag = '0'
            buyer.update_by = 'api'
            buyer.update_time = get_beijing_now()

            session.commit()
            logger.info(f"删除买入记录成功: {buyer_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除买入记录失败: {e}")
            return False
        finally:
            session.close()

    def get_pending_buyers(self) -> List[Dict[str, Any]]:
        """
        获取所有待处理的买入记录（状态为PENDING）
        :return: 待处理买入记录列表，按买入时间升序、ID升序排序
        """
        session = self.get_session()
        try:
            logger.info(f"查询待处理买入记录")
            buyers = session.query(FundBuyer).filter(
                FundBuyer.del_flag == '1',
                FundBuyer.buy_status == 'PENDING'
            ).order_by(FundBuyer.time.asc(), FundBuyer.id.asc()).all()
            
            result = []
            for buyer in buyers:
                result.append({
                    'id': buyer.id,
                    'fund_code': buyer.fund_code,
                    'fund_name': buyer.fund_name,
                    'time': str(buyer.time),
                    'amt': float(buyer.amt) if buyer.amt else 0.0,
                    'type': buyer.type,
                    'policy': buyer.policy,
                    'buy_status': buyer.buy_status,
                    'shares': float(buyer.shares) if buyer.shares else None,
                    'remark': buyer.remark
                })
            logger.info(f"查询到 {len(result)} 条待处理买入记录")
            return result
        finally:
            session.close()

    def process_buyer_transaction(self, buyer_ids: list, fund_code: str,
                                  buy_shares: float, buy_amt: float,
                                  current_price: float, buy_date: str) -> str:
        """
        原子化处理买入交易：累加持仓 + 回写买入记录份额/状态，单 session 单 commit。

        解决「先标记买入 SUCCESS 后更新持仓」的非原子性：原实现 update_buyer_shares 与
        update_position_by_buyer 各自 commit，若第二步失败，买入记录已 SUCCESS 而持仓未累加，
        该笔买入永远不会再被处理（已不在 PENDING 查询里），持仓永久漏加。本方法把两步合并为
        一个事务，任一步失败整体回滚，买入记录保持 PENDING 等待下次重试。与卖出侧
        process_seller_transaction 对称。

        幂等由 PENDING 状态机保证：get_pending_buyers 只取 PENDING 记录，每笔买入只处理一次，
        不再依赖 position.buy_date 做日期水位（原水位会误杀补录的历史/同日买入）。

        :param buyer_ids: 本次合并涉及的买入记录ID列表（同一天同一基金多笔合并）
        :param fund_code: 基金代码
        :param buy_shares: 本次买入份额（已合并）
        :param buy_amt: 本次买入金额（已合并，直接从流水传入避免浮点精度问题）
        :param current_price: 当前最新净值（买入当日净值，同时用于重算市值/盈亏与持仓 current_price）
        :param buy_date: 本次买入日期
        :return: 状态码
                 'SUCCESS' - 累加成功并已回写
                 'NO_POSITION' - 无持仓记录（买入记录仍标记 SUCCESS，因持仓不存在非异常）
                 'ERROR' - 异常（保持 PENDING，下次重试）
        """
        from .position_storage import Position
        session = self.get_session()
        try:
            # 1. 纯计算累加结果
            position = session.query(Position).filter(
                Position.fund_code == fund_code,
                Position.del_flag == '1'
            ).first()

            if not position:
                # 无持仓：买入份额照常标记 SUCCESS（持仓不存在非异常，不计入持仓）
                session.query(FundBuyer).filter(
                    FundBuyer.id.in_(buyer_ids),
                    FundBuyer.del_flag == '1'
                ).update({
                    FundBuyer.shares: buy_shares,
                    FundBuyer.buy_status: 'SUCCESS',
                    FundBuyer.update_by: 'system',
                    FundBuyer.update_time: get_beijing_now(),
                }, synchronize_session=False)
                session.commit()
                logger.info(f"买入交易 {buyer_ids}: 基金 {fund_code} 无持仓记录，仅标记买入 SUCCESS")
                return 'NO_POSITION'

            position_id = position.id
            old_shares = float(position.shares) if position.shares else 0.0
            old_cost_amount = float(position.cost_amount) if position.cost_amount else 0.0

            calc = _compute_buyer_accumulation(
                old_shares, old_cost_amount, buy_shares, buy_amt, current_price
            )

            # 2. 累加持仓（加权成本法）
            position.shares = calc['new_total_shares']
            position.cost_price = calc['weighted_cost_price']
            position.cost_amount = calc['new_cost_amount']
            position.current_price = current_price
            position.current_value = calc['current_value']
            position.profit_loss = calc['profit_loss']
            position.profit_loss_rate = calc['profit_loss_rate']
            position.buy_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
            position.update_by = 'system'
            position.update_time = get_beijing_now()

            # 3. 同事务回写买入记录份额/状态
            session.query(FundBuyer).filter(
                FundBuyer.id.in_(buyer_ids),
                FundBuyer.del_flag == '1'
            ).update({
                FundBuyer.shares: buy_shares,
                FundBuyer.buy_status: 'SUCCESS',
                FundBuyer.update_by: 'system',
                FundBuyer.update_time: get_beijing_now(),
            }, synchronize_session=False)

            session.commit()
            logger.info(
                f"买入交易 {buyer_ids} 原子完成: 持仓 {position_id} 原份额 {old_shares} + 买入 {buy_shares} "
                f"= 新份额 {calc['new_total_shares']}, 加权成本价 {calc['weighted_cost_price']:.4f}, "
                f"买入日期 {buy_date}"
            )
            return 'SUCCESS'
        except Exception as e:
            session.rollback()
            # 异常保持 PENDING，下次任务重试（避免误标 SUCCESS 导致永久漏加）
            logger.error(f"买入交易 {buyer_ids} 原子处理失败 (fund_code={fund_code}): {e}")
            return 'ERROR'
        finally:
            session.close()

    def get_buyers_with_pagination(self, fund_code=None, fund_name=None, buy_type=None, 
                                   buy_status=None, start_time=None, end_time=None,
                                   sort_field=None, sort_order=None, page=1, page_size=10):
        """
        获取买入记录列表（支持搜索、排序和分页）
        :param fund_code: 基金代码（模糊搜索）
        :param fund_name: 基金名称（模糊搜索）
        :param buy_type: 买入类型
        :param buy_status: 买入状态
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param sort_field: 排序字段
        :param sort_order: 排序方向（asc/desc）
        :param page: 页码
        :param page_size: 每页条数
        :return: (数据列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(FundBuyer).filter(FundBuyer.del_flag == '1')
            
            # 添加搜索条件
            if fund_code:
                query = query.filter(FundBuyer.fund_code.like(f'%{fund_code}%'))
            if fund_name:
                query = query.filter(FundBuyer.fund_name.like(f'%{fund_name}%'))
            if buy_type:
                query = query.filter(FundBuyer.type == buy_type)
            if buy_status:
                query = query.filter(FundBuyer.buy_status == buy_status)
            if start_time:
                query = query.filter(FundBuyer.time >= start_time)
            if end_time:
                query = query.filter(FundBuyer.time <= end_time)
            
            # 添加排序
            if sort_field and sort_order:
                field_map = {
                    'id': FundBuyer.id,
                    'fund_code': FundBuyer.fund_code,
                    'fund_name': FundBuyer.fund_name,
                    'time': FundBuyer.time,
                    'amt': FundBuyer.amt,
                    'type': FundBuyer.type,
                    'buy_status': FundBuyer.buy_status,
                    'policy': FundBuyer.policy,
                    'remark': FundBuyer.remark
                }
                if sort_field in field_map:
                    if sort_order == 'asc':
                        query = query.order_by(field_map[sort_field].asc())
                    else:
                        query = query.order_by(field_map[sort_field].desc())
            else:
                # 默认按时间降序排列
                query = query.order_by(FundBuyer.time.desc())
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            buyers = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for buyer in buyers:
                result.append({
                    'id': buyer.id,
                    'fund_code': buyer.fund_code,
                    'fund_name': buyer.fund_name,
                    'time': str(buyer.time),
                    'amt': float(buyer.amt) if buyer.amt else 0.0,
                    'type': buyer.type,
                    'policy': buyer.policy,
                    'buy_status': buyer.buy_status,
                    'shares': float(buyer.shares) if buyer.shares else None,
                    'remark': buyer.remark,
                    'create_time': str(buyer.create_time) if buyer.create_time else None,
                    'update_time': str(buyer.update_time) if buyer.update_time else None
                })
            
            return result, total
        finally:
            session.close()

