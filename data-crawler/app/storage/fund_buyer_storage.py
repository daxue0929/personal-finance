#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金买入流水数据存储层
"""

from datetime import datetime, date
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event

from ..utils.config import get_db_url
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base


class FundBuyer(Base):
    __tablename__ = 'fund_buyer'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False)
    fund_name = Column(String(64), default='')
    time = Column(Date, nullable=False, default=datetime.now().date())
    amt = Column(DECIMAL(7, 4), default=0.0000)
    type = Column(String(64), default='')
    policy = Column(String(500), default='')
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64), default='')
    create_time = Column(DateTime)
    update_by = Column(String(64), default='')
    update_time = Column(DateTime)
    remark = Column(String(500))
    buy_status = Column(String(20), default='PENDING')


class FundBuyerStorage:
    _engine = None
    _session_factory = None

    def __init__(self):
        self.engine = self._get_engine()
        self.Session = self._get_session_factory()
        self.session = self.Session()

    @classmethod
    def _get_engine(cls):
        if cls._engine is None:
            db_url = get_db_url()
            cls._engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                echo=False
            )

            @event.listens_for(cls._engine, 'connect')
            def set_timezone_on_connect(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET time_zone = '+08:00'")
                cursor.execute("SET NAMES utf8mb4")
                cursor.close()

        return cls._engine

    @classmethod
    def _get_session_factory(cls):
        if cls._session_factory is None:
            cls._session_factory = sessionmaker(bind=cls._get_engine())
        return cls._session_factory

    def get_all_buyers(self) -> List[FundBuyer]:
        """获取所有买入记录"""
        try:
            return self.session.query(FundBuyer).filter(
                FundBuyer.del_flag == '1'
            ).order_by(FundBuyer.time.desc()).all()
        except Exception as e:
            logger.error(f"获取买入记录失败: {e}")
            return []

    def get_buyer_by_id(self, buyer_id: int) -> Optional[FundBuyer]:
        """根据ID获取买入记录"""
        try:
            return self.session.query(FundBuyer).filter(
                FundBuyer.id == buyer_id,
                FundBuyer.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取买入记录 {buyer_id} 失败: {e}")
            return None

    def create_buyer(self, data: Dict[str, Any]) -> bool:
        """创建买入记录"""
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
            self.session.add(new_buyer)
            self.session.commit()
            self.session.refresh(new_buyer)
            logger.info(f"创建买入记录成功: {new_buyer.id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"创建买入记录失败: {e}")
            return False

    def update_buyer(self, buyer_id: int, data: Dict[str, Any]) -> bool:
        """更新买入记录"""
        try:
            buyer = self.get_buyer_by_id(buyer_id)
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
            if 'remark' in data:
                buyer.remark = data['remark']

            buyer.update_by = data.get('update_by', 'api')
            buyer.update_time = get_beijing_now()

            self.session.commit()
            logger.info(f"更新买入记录成功: {buyer_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"更新买入记录失败: {e}")
            return False

    def delete_buyer(self, buyer_id: int) -> bool:
        """删除买入记录（软删除）"""
        try:
            buyer = self.get_buyer_by_id(buyer_id)
            if not buyer:
                logger.warning(f"买入记录 {buyer_id} 不存在")
                return False

            buyer.del_flag = '0'
            buyer.update_by = 'api'
            buyer.update_time = get_beijing_now()

            self.session.commit()
            logger.info(f"删除买入记录成功: {buyer_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"删除买入记录失败: {e}")
            return False

    def close(self):
        if self.session:
            self.session.close()