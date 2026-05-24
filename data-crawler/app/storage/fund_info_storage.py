#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金信息数据存储层
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


class FundInfo(Base):
    __tablename__ = 'fund_info'

    fund_id = Column(BigInteger, primary_key=True, autoincrement=True)
    fund_code = Column(String(10), nullable=False, unique=True)
    fund_name = Column(String(64))
    fund_type = Column(String(20), default='混合型')
    net_asset_value = Column(DECIMAL(7, 4), default=0.0000)
    net_value_date = Column(Date)
    fund_manager = Column(String(64))
    establish_date = Column(Date)
    fund_size = Column(DECIMAL(15, 2), default=0.00)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)
    remark = Column(String(500))


class FundInfoStorage:
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

    def get_all_fund_codes(self) -> List[str]:
        try:
            fund_codes = self.session.query(FundInfo.fund_code).filter(
                FundInfo.del_flag == '1'
            ).all()
            return [code[0] for code in fund_codes]
        except Exception as e:
            logger.error(f"获取基金代码列表失败: {e}")
            return []

    def get_fund_by_code(self, fund_code: str) -> Optional[FundInfo]:
        try:
            return self.session.query(FundInfo).filter(
                FundInfo.fund_code == fund_code,
                FundInfo.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取基金 {fund_code} 信息失败: {e}")
            return None

    def update_fund_net_value(self, fund_code: str, net_asset_value: float,
                             net_value_date: str) -> bool:
        try:
            fund = self.get_fund_by_code(fund_code)
            if not fund:
                logger.warning(f"基金 {fund_code} 不存在，跳过更新")
                return False

            fund.net_asset_value = net_asset_value
            fund.net_value_date = datetime.strptime(net_value_date, '%Y-%m-%d').date()
            fund.update_time = get_beijing_now()
            fund.update_by = 'crawler'

            self.session.commit()
            logger.info(f"基金 {fund_code} 净值已更新: {net_asset_value} ({net_value_date})")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"更新基金 {fund_code} 净值失败: {e}")
            return False

    def batch_update_fund_net_values(self, fund_data_list: List[Dict[str, Any]]) -> Dict[str, int]:
        success_count = 0
        fail_count = 0

        for fund_data in fund_data_list:
            fund_code = fund_data.get('fund_code')
            net_value = fund_data.get('net_asset_value')
            net_date = fund_data.get('net_value_date')

            if not all([fund_code, net_value, net_date]):
                logger.warning(f"基金数据不完整，跳过: {fund_data}")
                fail_count += 1
                continue

            try:
                net_value_float = float(net_value)
            except ValueError:
                logger.warning(f"净值数据格式错误: {net_value}")
                fail_count += 1
                continue

            if self.update_fund_net_value(fund_code, net_value_float, net_date):
                success_count += 1
            else:
                fail_count += 1

        return {'success': success_count, 'failed': fail_count}

    def update_fund_remark(self, fund_code: str, remark: str) -> bool:
        try:
            fund = self.get_fund_by_code(fund_code)
            if not fund:
                logger.warning(f"基金 {fund_code} 不存在，跳过更新")
                return False

            fund.remark = remark
            fund.update_time = get_beijing_now()
            fund.update_by = 'crawler'

            self.session.commit()
            logger.info(f"基金 {fund_code} remark 已更新: {remark}")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"更新基金 {fund_code} remark 失败: {e}")
            return False

    def close(self):
        if self.session:
            self.session.close()
