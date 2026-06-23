#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数信息数据存储层
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


class IndexInfo(Base):
    __tablename__ = 'index_info'

    index_id = Column(BigInteger, primary_key=True, autoincrement=True)
    index_code = Column(String(10), nullable=False)
    index_name = Column(String(64))
    index_type = Column(String(20), default='宽基指数')
    trade_date = Column(Date, nullable=False)
    open_price = Column(DECIMAL(10, 2), default=0.00)
    close_price = Column(DECIMAL(10, 2), default=0.00)
    high_price = Column(DECIMAL(10, 2), default=0.00)
    low_price = Column(DECIMAL(10, 2), default=0.00)
    change_percent = Column(DECIMAL(6, 2), default=0.00)
    volume = Column(BigInteger, default=0)
    amount = Column(DECIMAL(20, 2), default=0.00)
    turnover_rate = Column(DECIMAL(6, 2), default=0.00)
    pe_ratio = Column(DECIMAL(8, 2), default=0.00)
    pe_percentile = Column(DECIMAL(5, 2), default=0.00)
    pb_ratio = Column(DECIMAL(8, 2), default=0.00)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)


class IndexInfoStorage:
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

    @classmethod
    def _get_session_factory(cls):
        if cls._session_factory is None:
            cls._session_factory = sessionmaker(bind=cls._get_engine())
        return cls._session_factory

    def get_all_index_codes(self) -> List[str]:
        try:
            index_codes = self.session.query(IndexInfo.index_code).filter(
                IndexInfo.del_flag == '1'
            ).distinct().all()
            return [code[0] for code in index_codes]
        except Exception as e:
            logger.error(f"获取指数代码列表失败: {e}")
            return []

    def get_index_by_code(self, index_code: str) -> Optional[IndexInfo]:
        try:
            return self.session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 信息失败: {e}")
            return None

    def get_index_by_code_and_date(self, index_code: str, trade_date: date) -> Optional[IndexInfo]:
        try:
            return self.session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.trade_date == trade_date,
                IndexInfo.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 在 {trade_date} 的数据失败: {e}")
            return None

    def get_latest_index_info(self, index_code: str) -> Optional[IndexInfo]:
        try:
            return self.session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.del_flag == '1'
            ).order_by(IndexInfo.trade_date.desc()).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 最新数据失败: {e}")
            return None

    def create_or_update_index_info(self, index_data: Dict[str, Any]) -> bool:
        try:
            index_code = index_data.get('index_code')
            trade_date = index_data.get('trade_date')

            if isinstance(trade_date, str):
                trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()

            existing = self.get_index_by_code_and_date(index_code, trade_date)

            if existing:
                existing.open_price = index_data.get('open_price', existing.open_price)
                existing.close_price = index_data.get('close_price', existing.close_price)
                existing.high_price = index_data.get('high_price', existing.high_price)
                existing.low_price = index_data.get('low_price', existing.low_price)
                existing.change_percent = index_data.get('change_percent', existing.change_percent)
                existing.volume = index_data.get('volume', existing.volume)
                existing.amount = index_data.get('amount', existing.amount)
                existing.turnover_rate = index_data.get('turnover_rate', existing.turnover_rate)
                existing.pe_ratio = index_data.get('pe_ratio', existing.pe_ratio)
                existing.pe_percentile = index_data.get('pe_percentile', existing.pe_percentile)
                existing.pb_ratio = index_data.get('pb_ratio', existing.pb_ratio)
                existing.update_time = get_beijing_now()
                existing.update_by = 'crawler'
                logger.info(f"指数 {index_code} 在 {trade_date} 的数据已更新")
            else:
                new_index = IndexInfo(
                    index_code=index_code,
                    index_name=index_data.get('index_name', ''),
                    index_type=index_data.get('index_type', '宽基指数'),
                    trade_date=trade_date,
                    open_price=index_data.get('open_price', 0.00),
                    close_price=index_data.get('close_price', 0.00),
                    high_price=index_data.get('high_price', 0.00),
                    low_price=index_data.get('low_price', 0.00),
                    change_percent=index_data.get('change_percent', 0.00),
                    volume=index_data.get('volume', 0),
                    amount=index_data.get('amount', 0.00),
                    turnover_rate=index_data.get('turnover_rate', 0.00),
                    pe_ratio=index_data.get('pe_ratio', 0.00),
                    pe_percentile=index_data.get('pe_percentile', 0.00),
                    pb_ratio=index_data.get('pb_ratio', 0.00),
                    create_by='crawler',
                    create_time=get_beijing_now()
                )
                self.session.add(new_index)
                logger.info(f"指数 {index_code} 在 {trade_date} 的数据已创建")

            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"创建/更新指数信息失败: {e}")
            return False

    def batch_create_or_update_index_info(self, index_data_list: List[Dict[str, Any]]) -> Dict[str, int]:
        success_count = 0
        fail_count = 0

        for index_data in index_data_list:
            if self.create_or_update_index_info(index_data):
                success_count += 1
            else:
                fail_count += 1

        return {'success': success_count, 'failed': fail_count}

    def close(self):
        if self.session:
            self.session.close()
