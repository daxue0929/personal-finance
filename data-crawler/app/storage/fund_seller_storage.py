#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金卖出流水数据存储层

与 fund_buyer_storage 镜像对称：
- 卖出录入的是「份额」shares（必填），卖出金额 amt 初始为空，由任务计算回写
- sell_status：PENDING 待处理 / SUCCESS 成功 / FAILED 失败
- 唯一键 (fund_code, time)：同一基金同一天仅一条卖出记录
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR, func

from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


def _compute_sell_reduction(old_shares, cost_price, old_cost_amount, sell_shares, nav):
    """纯计算：按加权平均成本法计算卖出后的持仓扣减与已实现盈亏（不依赖数据库，便于单元测试）。

    :return: dict
        - 超卖返回 {'ok': False}
        - 正常返回 {'ok': True, 'new_shares', 'new_cost_amount', 'realized_profit',
                   'current_value', 'profit_loss', 'profit_loss_rate'}
        - 全部卖出（new_shares==0）时 cost_amount/current_value/profit_loss/profit_loss_rate 强制归零
    """
    old_shares = float(old_shares)
    cost_price = float(cost_price)
    old_cost_amount = float(old_cost_amount)
    sell_shares = float(sell_shares)
    nav = float(nav)

    if sell_shares > old_shares:
        return {'ok': False}

    realized_profit = round((nav - cost_price) * sell_shares, 2)
    new_shares = old_shares - sell_shares
    new_cost_amount = old_cost_amount - sell_shares * cost_price

    if new_shares == 0:
        return {
            'ok': True,
            'new_shares': 0,
            'new_cost_amount': 0,
            'realized_profit': realized_profit,
            'current_value': 0,
            'profit_loss': 0,
            'profit_loss_rate': 0,
        }

    cost_amount_r = round(new_cost_amount, 2)
    current_value = round(new_shares * nav, 2)
    profit_loss = round(current_value - cost_amount_r, 2)
    profit_loss_rate = round(profit_loss / cost_amount_r * 100, 2) if cost_amount_r > 0 else 0
    return {
        'ok': True,
        'new_shares': new_shares,
        'new_cost_amount': cost_amount_r,
        'realized_profit': realized_profit,
        'current_value': current_value,
        'profit_loss': profit_loss,
        'profit_loss_rate': profit_loss_rate,
    }


class FundSeller(Base):
    __tablename__ = 'fund_seller'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    fund_name = Column(String(64), default='')
    time = Column(Date, nullable=False, default=datetime.now().date())
    shares = Column(DECIMAL(15, 4), default=0.0000)
    amt = Column(DECIMAL(15, 4), default=None)
    nav = Column(DECIMAL(7, 4), default=None)
    realized_profit = Column(DECIMAL(15, 2), default=None)
    type = Column(String(64), default='')
    policy = Column(String(500), default='')
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64), default='')
    create_time = Column(DateTime)
    update_by = Column(String(64), default='')
    update_time = Column(DateTime)
    remark = Column(String(500))
    sell_status = Column(String(20), default='PENDING')


class FundSellerStorage(StorageBase):
    """基金卖出流水数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_seller_by_id(self, seller_id: int) -> Optional[FundSeller]:
        """根据ID获取卖出记录"""
        session = self.get_session()
        try:
            return session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取卖出记录 {seller_id} 失败: {e}")
            return None
        finally:
            session.close()

    def create_seller(self, data: Dict[str, Any]) -> bool:
        """创建卖出记录"""
        session = self.get_session()
        try:
            new_seller = FundSeller(
                fund_code=data.get('fund_code', ''),
                fund_name=data.get('fund_name', ''),
                time=datetime.strptime(data.get('time'), '%Y-%m-%d').date() if data.get('time') else datetime.now().date(),
                shares=data.get('shares', 0.0),
                type=data.get('type', ''),
                policy=data.get('policy', ''),
                sell_status=data.get('sell_status', 'PENDING'),
                remark=data.get('remark', ''),
                del_flag='1',
                create_by=data.get('create_by', 'api'),
                create_time=get_beijing_now(),
                update_by=data.get('create_by', 'api'),
                update_time=get_beijing_now()
            )
            session.add(new_seller)
            session.commit()
            session.refresh(new_seller)
            logger.info(f"创建卖出记录成功: {new_seller.id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"创建卖出记录失败: {e}")
            return False
        finally:
            session.close()

    def update_seller(self, seller_id: int, data: Dict[str, Any]) -> bool:
        """更新卖出记录"""
        session = self.get_session()
        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()

            if not seller:
                logger.warning(f"卖出记录 {seller_id} 不存在")
                return False

            if 'fund_code' in data:
                seller.fund_code = data['fund_code']
            if 'fund_name' in data:
                seller.fund_name = data['fund_name']
            if 'time' in data:
                seller.time = datetime.strptime(data['time'], '%Y-%m-%d').date()
            if 'shares' in data:
                seller.shares = data['shares']
            if 'amt' in data:
                seller.amt = data['amt']
            if 'nav' in data:
                seller.nav = data['nav']
            if 'realized_profit' in data:
                seller.realized_profit = data['realized_profit']
            if 'type' in data:
                seller.type = data['type']
            if 'policy' in data:
                seller.policy = data['policy']
            if 'sell_status' in data:
                seller.sell_status = data['sell_status']
            if 'remark' in data:
                seller.remark = data['remark']

            seller.update_by = data.get('update_by', 'api')
            seller.update_time = get_beijing_now()

            session.commit()
            logger.info(f"更新卖出记录成功: {seller_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新卖出记录失败: {e}")
            return False
        finally:
            session.close()

    def delete_seller(self, seller_id: int) -> bool:
        """删除卖出记录（软删除）"""
        session = self.get_session()
        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()

            if not seller:
                logger.warning(f"卖出记录 {seller_id} 不存在")
                return False

            seller.del_flag = '0'
            seller.update_by = 'api'
            seller.update_time = get_beijing_now()

            session.commit()
            logger.info(f"删除卖出记录成功: {seller_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除卖出记录失败: {e}")
            return False
        finally:
            session.close()

    def get_pending_sellers(self) -> List[Dict[str, Any]]:
        """
        获取所有待处理的卖出记录（状态为PENDING）
        :return: 待处理卖出记录列表，按卖出时间升序、ID升序排序
        """
        session = self.get_session()
        try:
            logger.info(f"查询待处理卖出记录")
            sellers = session.query(FundSeller).filter(
                FundSeller.del_flag == '1',
                FundSeller.sell_status == 'PENDING'
            ).order_by(FundSeller.time.asc(), FundSeller.id.asc()).all()

            result = []
            for seller in sellers:
                result.append({
                    'id': seller.id,
                    'fund_code': seller.fund_code,
                    'fund_name': seller.fund_name,
                    'time': str(seller.time),
                    'shares': float(seller.shares) if seller.shares else 0.0,
                    'type': seller.type,
                    'policy': seller.policy,
                    'sell_status': seller.sell_status,
                    'remark': seller.remark
                })
            logger.info(f"查询到 {len(result)} 条待处理卖出记录")
            return result
        finally:
            session.close()

    def update_seller_status(self, seller_id: int, sell_status: str,
                             nav: float = None, amt: float = None,
                             realized_profit: float = None) -> bool:
        """
        仅更新卖出记录的状态（及可选的 nav/amt/realized_profit），不触碰持仓。

        用于卖出失败（无持仓/超卖/异常）时标记 FAILED 等不需扣减持仓的场景。
        单 session 单 commit。

        :return: True/False
        """
        session = self.get_session()
        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()

            if not seller:
                logger.warning(f"卖出记录 {seller_id} 不存在")
                return False

            seller.sell_status = sell_status
            if nav is not None:
                seller.nav = nav
            if amt is not None:
                seller.amt = amt
            if realized_profit is not None:
                seller.realized_profit = realized_profit
            seller.update_by = 'system'
            seller.update_time = get_beijing_now()

            session.commit()
            logger.info(f"更新卖出记录 {seller_id} 状态: {sell_status}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新卖出记录 {seller_id} 状态失败: {e}")
            return False
        finally:
            session.close()

    def process_seller_transaction(self, seller_id: int, fund_code: str,
                                   sell_shares: float, nav: float, amt: float) -> str:
        """
        原子化处理卖出交易：扣减持仓 + 回写卖出金额/净值/已实现盈亏/状态，单 session 单 commit。

        解决「先扣持仓后置状态」的非原子性问题：若分两步各自 commit，第二步失败会导致
        卖出记录仍 PENDING 而持仓已扣减，下次任务重复扣减。本方法把两步合并为一个事务，
        任一步失败整体回滚，卖出记录保持 PENDING 等待下次重试。

        :param seller_id: 卖出记录ID
        :param fund_code: 基金代码
        :param sell_shares: 卖出份额
        :param nav: 卖出当日净值
        :param amt: 卖出金额（份额×净值）
        :return: 状态码
                 'SUCCESS' - 扣减成功并已回写
                 'NO_POSITION' - 无持仓记录（已标记 FAILED）
                 'OVERSELL' - 卖出份额超过持仓份额（已标记 FAILED）
                 'ERROR' - 异常（保持 PENDING，下次重试）
        """
        from .position_storage import Position
        session = self.get_session()
        try:
            seller = session.query(FundSeller).filter(
                FundSeller.id == seller_id,
                FundSeller.del_flag == '1'
            ).first()
            if not seller:
                logger.warning(f"卖出记录 {seller_id} 不存在")
                return 'ERROR'

            position = session.query(Position).filter(
                Position.fund_code == fund_code,
                Position.del_flag == '1'
            ).first()

            # 无持仓 -> 标记 FAILED，不扣减
            if not position:
                seller.sell_status = 'FAILED'
                seller.update_by = 'system'
                seller.update_time = get_beijing_now()
                session.commit()
                logger.warning(f"卖出记录 {seller_id}: 基金 {fund_code} 无持仓记录，标记 FAILED")
                return 'NO_POSITION'

            position_id = position.id
            old_shares = float(position.shares) if position.shares else 0.0
            cost_price = float(position.cost_price) if position.cost_price else 0.0
            old_cost_amount = float(position.cost_amount) if position.cost_amount else 0.0

            # 纯计算扣减结果（加权成本法）
            calc = _compute_sell_reduction(old_shares, cost_price, old_cost_amount, sell_shares, nav)

            # 超卖 -> 标记 FAILED，不扣减
            if not calc['ok']:
                seller.sell_status = 'FAILED'
                seller.update_by = 'system'
                seller.update_time = get_beijing_now()
                session.commit()
                logger.warning(
                    f"卖出记录 {seller_id}: 持仓 {position_id} 卖出超限，持仓份额 {old_shares} < 卖出份额 {sell_shares}，标记 FAILED"
                )
                return 'OVERSELL'

            realized_profit = calc['realized_profit']

            # 扣减份额与成本金额（加权成本法：cost_price 不变）
            position.shares = calc['new_shares']
            position.cost_amount = calc['new_cost_amount']
            position.current_price = nav
            position.current_value = calc['current_value']
            position.profit_loss = calc['profit_loss']
            position.profit_loss_rate = calc['profit_loss_rate']
            position.update_by = 'system'
            position.update_time = get_beijing_now()

            # 同事务回写卖出记录金额/净值/已实现盈亏/状态
            seller.amt = amt
            seller.nav = nav
            seller.realized_profit = realized_profit
            seller.sell_status = 'SUCCESS'
            seller.update_by = 'system'
            seller.update_time = get_beijing_now()

            session.commit()
            logger.info(
                f"卖出交易 {seller_id} 原子完成: 持仓 {position_id} 原份额 {old_shares} - 卖出 {sell_shares} = 新份额 {calc['new_shares']}, "
                f"成本价 {cost_price:.4f}(不变), 卖出净值 {nav:.4f}, 金额 {amt}, 已实现盈亏 {realized_profit}"
            )
            return 'SUCCESS'
        except Exception as e:
            session.rollback()
            # 异常保持 PENDING，下次任务重试（避免误判为超卖永久 FAILED）
            logger.error(f"卖出交易 {seller_id} 原子处理失败 (fund_code={fund_code}): {e}")
            return 'ERROR'
        finally:
            session.close()

    def get_sellers_with_pagination(self, fund_code=None, fund_name=None, sell_type=None,
                                    sell_status=None, start_time=None, end_time=None,
                                    sort_field=None, sort_order=None, page=1, page_size=10):
        """
        获取卖出记录列表（支持搜索、排序和分页）
        :param fund_code: 基金代码（模糊搜索）
        :param fund_name: 基金名称（模糊搜索）
        :param sell_type: 卖出类型
        :param sell_status: 卖出状态
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
            query = session.query(FundSeller).filter(FundSeller.del_flag == '1')

            # 添加搜索条件
            if fund_code:
                query = query.filter(FundSeller.fund_code.like(f'%{fund_code}%'))
            if fund_name:
                query = query.filter(FundSeller.fund_name.like(f'%{fund_name}%'))
            if sell_type:
                query = query.filter(FundSeller.type == sell_type)
            if sell_status:
                query = query.filter(FundSeller.sell_status == sell_status)
            if start_time:
                query = query.filter(FundSeller.time >= start_time)
            if end_time:
                query = query.filter(FundSeller.time <= end_time)

            # 添加排序
            if sort_field and sort_order:
                field_map = {
                    'id': FundSeller.id,
                    'fund_code': FundSeller.fund_code,
                    'fund_name': FundSeller.fund_name,
                    'time': FundSeller.time,
                    'shares': FundSeller.shares,
                    'amt': FundSeller.amt,
                    'nav': FundSeller.nav,
                    'realized_profit': FundSeller.realized_profit,
                    'type': FundSeller.type,
                    'sell_status': FundSeller.sell_status,
                    'remark': FundSeller.remark
                }
                if sort_field in field_map:
                    if sort_order == 'asc':
                        query = query.order_by(field_map[sort_field].asc())
                    else:
                        query = query.order_by(field_map[sort_field].desc())
            else:
                # 默认按时间降序排列
                query = query.order_by(FundSeller.time.desc())

            # 获取总数
            total = query.count()

            # 分页查询
            sellers = query.offset((page - 1) * page_size).limit(page_size).all()

            result = []
            for seller in sellers:
                result.append({
                    'id': seller.id,
                    'fund_code': seller.fund_code,
                    'fund_name': seller.fund_name,
                    'time': str(seller.time),
                    'shares': float(seller.shares) if seller.shares else 0.0,
                    'amt': float(seller.amt) if seller.amt is not None else None,
                    'nav': float(seller.nav) if seller.nav is not None else None,
                    'realized_profit': float(seller.realized_profit) if seller.realized_profit is not None else None,
                    'type': seller.type,
                    'policy': seller.policy,
                    'sell_status': seller.sell_status,
                    'remark': seller.remark,
                    'create_time': str(seller.create_time) if seller.create_time else None,
                    'update_time': str(seller.update_time) if seller.update_time else None
                })

            return result, total
        finally:
            session.close()

    def get_realized_profit_total(self, fund_code: Optional[str] = None) -> float:
        """
        获取累计已实现盈亏
        :param fund_code: 指定基金代码时只统计该基金（单持仓视角）；None 为全部卖出汇总（组合视角）
        :return: SUM(realized_profit)，无数据返回 0.0
        """
        session = self.get_session()
        try:
            query = session.query(func.sum(FundSeller.realized_profit)).filter(
                FundSeller.del_flag == '1',
                FundSeller.sell_status == 'SUCCESS'
            )
            if fund_code:
                query = query.filter(FundSeller.fund_code == fund_code)
            total = query.scalar()
            return float(total) if total is not None else 0.0
        except Exception as e:
            logger.error(f"获取累计已实现盈亏失败: {e}")
            return 0.0
        finally:
            session.close()
