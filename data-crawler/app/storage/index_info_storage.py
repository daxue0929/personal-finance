#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数信息数据存储层
"""

from datetime import datetime, date
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
    source = Column(String(32), default='腾讯财经')
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)


class IndexInfoStorage(StorageBase):
    """指数信息数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_all_index_codes(self) -> List[str]:
        session = self.get_session()
        try:
            index_codes = session.query(IndexInfo.index_code).filter(
                IndexInfo.del_flag == '1'
            ).distinct().all()
            return [code[0] for code in index_codes]
        except Exception as e:
            logger.error(f"获取指数代码列表失败: {e}")
            return []
        finally:
            session.close()

    def get_index_by_code(self, index_code: str) -> Optional[IndexInfo]:
        session = self.get_session()
        try:
            return session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 信息失败: {e}")
            return None
        finally:
            session.close()

    def get_index_by_code_and_date(self, index_code: str, trade_date: date) -> Optional[IndexInfo]:
        session = self.get_session()
        try:
            return session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.trade_date == trade_date,
                IndexInfo.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 在 {trade_date} 的数据失败: {e}")
            return None
        finally:
            session.close()

    def get_latest_index_info(self, index_code: str) -> Optional[IndexInfo]:
        session = self.get_session()
        try:
            return session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.del_flag == '1'
            ).order_by(IndexInfo.trade_date.desc()).first()
        except Exception as e:
            logger.error(f"获取指数 {index_code} 最新数据失败: {e}")
            return None
        finally:
            session.close()

    def get_all_indexes(self) -> List[Dict[str, Any]]:
        """获取所有指数（去重，下拉选项用）：[{index_code, index_name, index_type}]"""
        session = self.get_session()
        try:
            rows = session.query(
                IndexInfo.index_code, IndexInfo.index_name, IndexInfo.index_type
            ).filter(IndexInfo.del_flag == '1').distinct().all()
            return [{'index_code': r[0], 'index_name': r[1], 'index_type': r[2]} for r in rows]
        except Exception as e:
            logger.error(f"获取指数列表失败: {e}")
            return []
        finally:
            session.close()

    def get_index_list_with_pagination(self, index_code=None, index_name=None,
                                       index_type=None, start_date=None, end_date=None,
                                       page=1, page_size=10):
        """指数信息分页查询（列表页用）。返回 (list, total)，按日期降序。"""
        session = self.get_session()
        try:
            query = session.query(IndexInfo).filter(IndexInfo.del_flag == '1')
            if index_code:
                query = query.filter(IndexInfo.index_code == index_code)
            if index_name:
                query = query.filter(IndexInfo.index_name.like(f'%{index_name}%'))
            if index_type:
                query = query.filter(IndexInfo.index_type == index_type)
            if start_date:
                query = query.filter(IndexInfo.trade_date >= start_date)
            if end_date:
                query = query.filter(IndexInfo.trade_date <= end_date)

            total = query.count()
            rows = query.order_by(IndexInfo.trade_date.desc()) \
                        .offset((page - 1) * page_size).limit(page_size).all()
            return [self._to_dict(r) for r in rows], total
        finally:
            session.close()

    def get_index_history(self, index_code, start_date=None, end_date=None):
        """获取某指数区间内全部日线（分析用，按日期升序）。"""
        session = self.get_session()
        try:
            query = session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.del_flag == '1'
            )
            if start_date:
                query = query.filter(IndexInfo.trade_date >= start_date)
            if end_date:
                query = query.filter(IndexInfo.trade_date <= end_date)
            rows = query.order_by(IndexInfo.trade_date.asc()).all()
            return [self._to_dict(r) for r in rows]
        finally:
            session.close()

    def _to_dict(self, row) -> Dict[str, Any]:
        """行转字典（DECIMAL/Date 转 float/str，前端友好）"""
        return {
            'index_id': row.index_id,
            'index_code': row.index_code,
            'index_name': row.index_name,
            'index_type': row.index_type,
            'trade_date': str(row.trade_date) if row.trade_date else None,
            'open_price': float(row.open_price) if row.open_price is not None else 0.0,
            'close_price': float(row.close_price) if row.close_price is not None else 0.0,
            'high_price': float(row.high_price) if row.high_price is not None else 0.0,
            'low_price': float(row.low_price) if row.low_price is not None else 0.0,
            'change_percent': float(row.change_percent) if row.change_percent is not None else 0.0,
            'volume': int(row.volume) if row.volume is not None else 0,
            'amount': float(row.amount) if row.amount is not None else 0.0,
            'turnover_rate': float(row.turnover_rate) if row.turnover_rate is not None else 0.0,
            'pe_ratio': float(row.pe_ratio) if row.pe_ratio is not None else 0.0,
            'pe_percentile': float(row.pe_percentile) if row.pe_percentile is not None else 0.0,
            'pb_ratio': float(row.pb_ratio) if row.pb_ratio is not None else 0.0,
            'source': row.source or '',
        }

    def create_or_update_index_info(self, index_data: Dict[str, Any]) -> bool:
        session = self.get_session()
        try:
            index_code = index_data.get('index_code')
            trade_date = index_data.get('trade_date')

            if isinstance(trade_date, str):
                trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()

            existing = session.query(IndexInfo).filter(
                IndexInfo.index_code == index_code,
                IndexInfo.trade_date == trade_date,
                IndexInfo.del_flag == '1'
            ).first()

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
                if index_data.get('source'):
                    existing.source = index_data.get('source')
                existing.update_time = get_beijing_now()
                existing.update_by = 'crawler'
                logger.info(f"指数 {index_code} 在 {trade_date} 的数据已更新")
            else:
                # 4 道 name 兜底（PRD "index-basic-table" §AC-2 T2.8）：
                # 优先级：index_data > index_basic(DB) > INDEX_NAME_MAP(parser) > 历史 index_info > ''
                # 每道独立 try/except，失败降级到下一道，不中断主流程。
                name = index_data.get('index_name', '')

                # 兜底 1：入参已有 name 则跳过（最高优先级）
                if not name:
                    # 兜底 2：查 index_basic 元表（DB 真源）
                    try:
                        from .index_basic_storage import IndexBasicStorage
                        basic_row = IndexBasicStorage().get(index_code)
                        if basic_row and basic_row.index_name:
                            name = basic_row.index_name
                    except Exception as e:
                        logger.warning(f"查询 index_basic {index_code} 失败，降级到下一道: {e}")

                # 兜底 3：查 parser 内置 INDEX_NAME_MAP
                if not name:
                    try:
                        from ..parser.kc_index_parser import KcIndexParser
                        name = KcIndexParser.INDEX_NAME_MAP.get(index_code, '')
                    except Exception as e:
                        logger.warning(f"查 KcIndexParser.INDEX_NAME_MAP 失败，降级到下一道: {e}")

                # 兜底 4：查历史 index_info 最近一条非空 name（保留原兜底）
                if not name:
                    try:
                        prev = session.query(IndexInfo.index_name).filter(
                            IndexInfo.index_code == index_code,
                            IndexInfo.del_flag == '1',
                            IndexInfo.index_name.isnot(None),
                            IndexInfo.index_name != ''
                        ).order_by(IndexInfo.trade_date.desc()).first()
                        if prev:
                            name = prev[0]
                    except Exception as e:
                        logger.warning(f"查历史 index_info name 失败: {e}")

                new_index = IndexInfo(
                    index_code=index_code,
                    index_name=name,
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
                    source=index_data.get('source', '腾讯财经'),
                    create_by='crawler',
                    create_time=get_beijing_now()
                )
                session.add(new_index)
                logger.info(f"指数 {index_code} 在 {trade_date} 的数据已创建")

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"创建/更新指数信息失败: {e}")
            return False
        finally:
            session.close()

    def batch_create_or_update_index_info(self, index_data_list: List[Dict[str, Any]]) -> Dict[str, int]:
        success_count = 0
        fail_count = 0

        for index_data in index_data_list:
            if self.create_or_update_index_info(index_data):
                success_count += 1
            else:
                fail_count += 1

        return {'success': success_count, 'failed': fail_count}


