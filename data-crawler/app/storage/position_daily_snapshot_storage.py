#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓每日快照存储层

提供持仓快照的查询与应用层备份。遵循全库 Storage 约定：
- ORM 模型继承 Base，Storage 类继承 StorageBase（自动加日志）
- 金额用 DECIMAL，时间用 get_beijing_now()
- 盈亏公式与存储过程 backup_position_daily_snapshot 保持一致：
    current_value = shares × net_asset_value
    profit_loss   = current_value - cost_amount
    profit_loss_rate = profit_loss / cost_amount × 100
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, BigInteger, String, Date, DateTime, DECIMAL, text, func

from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


class PositionDailySnapshot(Base):
    """持仓每日快照实体类"""
    __tablename__ = 'position_daily_snapshot'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, default=1, index=True, comment='所属 user（multi-user 隔离，从 position 携带）')
    position_id = Column(BigInteger, nullable=False, comment='持仓ID')
    snapshot_date = Column(Date, nullable=False, comment='快照日期')
    fund_code = Column(String(10), nullable=False, comment='基金代码')
    fund_name = Column(String(64), default='', comment='基金名称')
    shares = Column(DECIMAL(15, 4), default=0)
    cost_price = Column(DECIMAL(7, 4), default=0)
    current_price = Column(DECIMAL(7, 4), default=0)
    cost_amount = Column(DECIMAL(15, 2), default=0)
    current_value = Column(DECIMAL(15, 2), default=0)
    profit_loss = Column(DECIMAL(15, 2), default=0)
    profit_loss_rate = Column(DECIMAL(6, 2), default=0)
    source = Column(String(20), default='manual', comment='数据来源（manual/system）')
    create_time = Column(DateTime, default=get_beijing_now)


def _to_dict(item: PositionDailySnapshot) -> Dict[str, Any]:
    """快照实体转字典"""
    return {
        'id': item.id,
        'position_id': item.position_id,
        'snapshot_date': str(item.snapshot_date) if item.snapshot_date else None,
        'fund_code': item.fund_code,
        'fund_name': item.fund_name or '',
        'shares': float(item.shares) if item.shares else 0.0,
        'cost_price': float(item.cost_price) if item.cost_price else 0.0,
        'current_price': float(item.current_price) if item.current_price else 0.0,
        'cost_amount': float(item.cost_amount) if item.cost_amount else 0.0,
        'current_value': float(item.current_value) if item.current_value else 0.0,
        'profit_loss': float(item.profit_loss) if item.profit_loss else 0.0,
        'profit_loss_rate': float(item.profit_loss_rate) if item.profit_loss_rate else 0.0,
        'source': item.source,
        'create_time': str(item.create_time) if item.create_time else None,
    }


class PositionDailySnapshotStorage(StorageBase):
    """持仓每日快照存储类"""

    def __init__(self):
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        return self.Session()

    def get_position_options(self) -> List[Dict[str, Any]]:
        """获取有快照数据的可选持仓列表（供分析页下拉）。

        返回快照表中出现过的 distinct (position_id, fund_code, fund_name)，
        并 outerjoin position 表补 index_code（关联指数，供「指数分析」跳转）。
        按 position_id 升序。无数据返回空列表。
        """
        from .position_storage import Position
        session = self.get_session()
        try:
            rows = session.query(
                PositionDailySnapshot.position_id,
                PositionDailySnapshot.fund_code,
                PositionDailySnapshot.fund_name,
                Position.index_code
            ).outerjoin(
                Position, Position.id == PositionDailySnapshot.position_id
            ).distinct().order_by(PositionDailySnapshot.position_id.asc()).all()
            return [{
                'position_id': r[0],
                'fund_code': r[1],
                'fund_name': r[2] or '',
                'index_code': r[3]
            } for r in rows]
        finally:
            session.close()

    def get_position_snapshot_series(self, position_id: int,
                                     start_date: Optional[str] = None,
                                     end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取单持仓的快照序列（按日期升序），供持仓分析。

        :param position_id: 持仓ID
        :param start_date: 起始日期（YYYY-MM-DD，可选）
        :param end_date: 结束日期（YYYY-MM-DD，可选）
        :return: 快照字典列表（升序）
        """
        session = self.get_session()
        try:
            query = session.query(PositionDailySnapshot) \
                .filter(PositionDailySnapshot.position_id == position_id)
            if start_date:
                query = query.filter(PositionDailySnapshot.snapshot_date >= start_date)
            if end_date:
                query = query.filter(PositionDailySnapshot.snapshot_date <= end_date)
            items = query.order_by(PositionDailySnapshot.snapshot_date.asc()).all()
            return [_to_dict(i) for i in items]
        finally:
            session.close()

    def get_latest_snapshot_all_positions(self) -> List[Dict[str, Any]]:
        """获取最新快照日的全部持仓快照（供持仓占比饼图）。

        取 position_daily_snapshot 中最大 snapshot_date 当天的所有记录。
        无数据返回空列表。
        """
        session = self.get_session()
        try:
            latest_date = session.query(func.max(PositionDailySnapshot.snapshot_date)).scalar()
            if not latest_date:
                return []
            items = session.query(PositionDailySnapshot) \
                .filter(PositionDailySnapshot.snapshot_date == latest_date) \
                .all()
            return [_to_dict(i) for i in items]
        finally:
            session.close()

    def get_portfolio_snapshot_series(self, start_date: Optional[str] = None,
                                      end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取组合级每日聚合快照序列（按 snapshot_date 升序），供累计收益图。

        按快照日期分组，对所有持仓求和：SUM(current_value)/SUM(cost_amount)/SUM(profit_loss)，
        盈亏率 = SUM(profit_loss)/SUM(cost_amount)×100（未舍入中间值再 round）。
        与单持仓序列口径一致，便于前端单持仓/组合视角切换复用同一渲染逻辑。

        :param start_date: 起始日期（YYYY-MM-DD，可选）
        :param end_date: 结束日期（YYYY-MM-DD，可选）
        :return: 每日聚合字典列表（升序），每项含
                 snapshot_date/current_value/cost_amount/profit_loss/profit_loss_rate
        """
        session = self.get_session()
        try:
            query = session.query(
                PositionDailySnapshot.snapshot_date,
                func.sum(PositionDailySnapshot.current_value).label('current_value'),
                func.sum(PositionDailySnapshot.cost_amount).label('cost_amount'),
                func.sum(PositionDailySnapshot.profit_loss).label('profit_loss'),
            ).group_by(PositionDailySnapshot.snapshot_date)
            if start_date:
                query = query.filter(PositionDailySnapshot.snapshot_date >= start_date)
            if end_date:
                query = query.filter(PositionDailySnapshot.snapshot_date <= end_date)
            rows = query.order_by(PositionDailySnapshot.snapshot_date.asc()).all()

            result = []
            for r in rows:
                current_value = float(r.current_value) if r.current_value is not None else 0.0
                cost_amount = float(r.cost_amount) if r.cost_amount is not None else 0.0
                profit_loss = float(r.profit_loss) if r.profit_loss is not None else 0.0
                profit_loss_rate = round(profit_loss / cost_amount * 100, 2) if cost_amount > 0 else 0.0
                result.append({
                    'snapshot_date': str(r.snapshot_date) if r.snapshot_date else None,
                    'current_value': current_value,
                    'cost_amount': cost_amount,
                    'profit_loss': profit_loss,
                    'profit_loss_rate': profit_loss_rate,
                })
            return result
        finally:
            session.close()

    def get_snapshots_with_pagination(self, user_id=None, position_id=None, fund_code=None,
                                      start_date=None, end_date=None,
                                      page=1, page_size=10):
        """分页查询快照列表（供管理/调试）
        :param user_id: 限定 user；None = 不过滤（admin 跨用户视角）
        """
        session = self.get_session()
        try:
            query = session.query(PositionDailySnapshot)
            if user_id is not None:
                query = query.filter(PositionDailySnapshot.user_id == user_id)
            if position_id is not None:
                query = query.filter(PositionDailySnapshot.position_id == position_id)
            if fund_code:
                query = query.filter(PositionDailySnapshot.fund_code == fund_code)
            if start_date:
                query = query.filter(PositionDailySnapshot.snapshot_date >= start_date)
            if end_date:
                query = query.filter(PositionDailySnapshot.snapshot_date <= end_date)
            total = query.count()
            items = query.order_by(PositionDailySnapshot.snapshot_date.desc()) \
                .offset((page - 1) * page_size).limit(page_size).all()
            return [_to_dict(i) for i in items], total
        finally:
            session.close()

    def upsert_snapshot(self, position_id: int, snapshot_date, fund_code, fund_name,
                        shares, cost_price, current_price, cost_amount,
                        current_value, profit_loss, profit_loss_rate, source='manual'):
        """应用层 upsert 单条快照（查 position_id+snapshot_date，存在则更新，否则插入）。

        供手动补录或应用层批量备份使用。
        """
        session = self.get_session()
        try:
            existing = session.query(PositionDailySnapshot).filter(
                PositionDailySnapshot.position_id == position_id,
                PositionDailySnapshot.snapshot_date == snapshot_date
            ).first()
            if existing:
                existing.fund_code = fund_code
                existing.fund_name = fund_name
                existing.shares = shares
                existing.cost_price = cost_price
                existing.current_price = current_price
                existing.cost_amount = cost_amount
                existing.current_value = current_value
                existing.profit_loss = profit_loss
                existing.profit_loss_rate = profit_loss_rate
                existing.source = source
                existing.create_time = get_beijing_now()
            else:
                session.add(PositionDailySnapshot(
                    position_id=position_id, snapshot_date=snapshot_date,
                    fund_code=fund_code, fund_name=fund_name,
                    shares=shares, cost_price=cost_price, current_price=current_price,
                    cost_amount=cost_amount, current_value=current_value,
                    profit_loss=profit_loss, profit_loss_rate=profit_loss_rate,
                    source=source, create_time=get_beijing_now()
                ))
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"upsert 持仓快照失败 (position_id={position_id}, date={snapshot_date}): {e}")
            raise e
        finally:
            session.close()

    def backup_snapshots_app_layer(self, snapshot_date=None) -> int:
        """应用层批量备份（主路径，由定时任务调用）。

        盈亏按 fund_info.net_asset_value 重算，公式与存储过程 backup_position_daily_snapshot 一致：
            current_value = shares × net_asset_value
            profit_loss   = current_value - cost_amount
            profit_loss_rate = profit_loss / cost_amount × 100
        净值回退语义与存储过程 IFNULL 对齐：仅 fund_info.net_asset_value 为 NULL 时回退到 position.current_price。

        单 session 单次 commit，保证当日快照原子写入（失败整体回滚）。

        :param snapshot_date: 快照日期（YYYY-MM-DD 或 date），默认昨天
        :return: 备份的记录数
        """
        from .position_storage import Position
        from .fund_info_storage import FundInfo
        if snapshot_date is None:
            snapshot_date = (get_beijing_now() - timedelta(days=1)).date()
        snapshot_date_str = str(snapshot_date)

        session = self.get_session()
        try:
            # 取全部有效持仓（del_flag='1'，份额>0）
            positions = session.query(Position).filter(
                Position.del_flag == '1', Position.shares > 0
            ).all()
            if not positions:
                logger.info("无有效持仓，跳过快照备份")
                return 0

            # 取所有涉及基金的最新净值（fund_code -> net_asset_value 或 None）
            fund_codes = {p.fund_code for p in positions}
            nav_map = {}
            if fund_codes:
                funds = session.query(FundInfo).filter(
                    FundInfo.fund_code.in_(fund_codes), FundInfo.del_flag == '1'
                ).all()
                # 显式 None 判断：与 SQL IFNULL 对齐，net_asset_value 为 NULL 才映射 None（0 不回退）
                nav_map = {
                    f.fund_code: (float(f.net_asset_value) if f.net_asset_value is not None else None)
                    for f in funds
                }

            # 一次性取出当日已存在的快照，内存判断 upsert，单次 commit 保证原子性
            existing_map = {
                s.position_id: s for s in session.query(PositionDailySnapshot).filter(
                    PositionDailySnapshot.snapshot_date == snapshot_date_str
                ).all()
            }

            now = get_beijing_now()
            count = 0
            for p in positions:
                shares = float(p.shares) if p.shares else 0.0
                cost_amount = float(p.cost_amount) if p.cost_amount else 0.0
                cost_price = float(p.cost_price) if p.cost_price else 0.0
                position_current_price = float(p.current_price) if p.current_price else 0.0
                # 当日净值：fund_info 为 NULL 才回退（与存储过程 IFNULL 对齐）
                nav = nav_map.get(p.fund_code)
                if nav is None:
                    nav = position_current_price

                # 用未舍入中间值算 rate，与存储过程 ROUND((shares*nav - cost_amount)/cost_amount*100, 2) 对齐
                raw_current_value = shares * nav
                raw_profit_loss = raw_current_value - cost_amount
                current_value = round(raw_current_value, 2)
                profit_loss = round(raw_profit_loss, 2)
                profit_loss_rate = round(raw_profit_loss / cost_amount * 100, 2) if cost_amount > 0 else 0.0

                existing = existing_map.get(p.id)
                if existing:
                    existing.fund_code = p.fund_code
                    existing.fund_name = p.fund_name or ''
                    existing.shares = shares
                    existing.cost_price = cost_price
                    existing.current_price = nav
                    existing.cost_amount = cost_amount
                    existing.current_value = current_value
                    existing.profit_loss = profit_loss
                    existing.profit_loss_rate = profit_loss_rate
                    existing.source = 'system'
                    existing.create_time = now
                else:
                    session.add(PositionDailySnapshot(
                        position_id=p.id, snapshot_date=snapshot_date_str,
                        fund_code=p.fund_code, fund_name=p.fund_name or '',
                        shares=shares, cost_price=cost_price, current_price=nav,
                        cost_amount=cost_amount, current_value=current_value,
                        profit_loss=profit_loss, profit_loss_rate=profit_loss_rate,
                        source='system', create_time=now
                    ))
                count += 1
            session.commit()
            logger.info(f"应用层快照备份完成：{snapshot_date_str}，共 {count} 条")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"应用层快照备份失败 ({snapshot_date_str}): {e}")
            raise e
        finally:
            session.close()

    def backup_snapshots_via_procedure(self) -> int:
        """调用存储过程备份（次要路径，供 DBA 手动运维）。

        存储过程内部已处理删除重复+插入，幂等。
        """
        session = self.get_session()
        try:
            result = session.execute(text("CALL backup_position_daily_snapshot()"))
            session.commit()
            for row in result:
                return row[0] if row else 0
            return 0
        except Exception as e:
            session.rollback()
            logger.error(f"调用快照备份存储过程失败: {e}")
            raise e
        finally:
            session.close()
