#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金信息数据存储层
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


class FundInfoStorage(StorageBase):
    """基金信息数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_all_fund_codes(self) -> List[str]:
        session = self.get_session()
        try:
            fund_codes = session.query(FundInfo.fund_code).filter(
                FundInfo.del_flag == '1'
            ).all()
            return [code[0] for code in fund_codes]
        except Exception as e:
            logger.error(f"获取基金代码列表失败: {e}")
            return []
        finally:
            session.close()

    def get_fund_by_code(self, fund_code: str) -> Optional[FundInfo]:
        session = self.get_session()
        try:
            return session.query(FundInfo).filter(
                FundInfo.fund_code == fund_code,
                FundInfo.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取基金 {fund_code} 信息失败: {e}")
            return None
        finally:
            session.close()

    def update_fund_net_value(self, fund_code: str, net_asset_value: float,
                             net_value_date: str) -> bool:
        session = self.get_session()
        try:
            fund = session.query(FundInfo).filter(
                FundInfo.fund_code == fund_code,
                FundInfo.del_flag == '1'
            ).first()
            
            if not fund:
                logger.warning(f"基金 {fund_code} 不存在，跳过更新")
                return False

            fund.net_asset_value = net_asset_value
            fund.net_value_date = datetime.strptime(net_value_date, '%Y-%m-%d').date()
            fund.update_time = get_beijing_now()
            fund.update_by = 'crawler'

            session.commit()
            logger.info(f"基金 {fund_code} 净值已更新: {net_asset_value} ({net_value_date})")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"更新基金 {fund_code} 净值失败: {e}")
            return False
        finally:
            session.close()

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

    def get_funds_with_pagination(self, fund_code=None, fund_name=None, fund_type=None, page=1, page_size=10):
        """
        获取基金信息列表（支持搜索和分页）
        :param fund_code: 基金代码（模糊搜索）
        :param fund_name: 基金名称（模糊搜索）
        :param fund_type: 基金类型
        :param page: 页码
        :param page_size: 每页条数
        :return: (数据列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(FundInfo).filter(FundInfo.del_flag == '1')
            
            # 添加搜索条件
            if fund_code:
                query = query.filter(FundInfo.fund_code.like(f'%{fund_code}%'))
            if fund_name:
                query = query.filter(FundInfo.fund_name.like(f'%{fund_name}%'))
            if fund_type:
                query = query.filter(FundInfo.fund_type == fund_type)
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            funds = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for fund in funds:
                result.append({
                    'fund_id': fund.fund_id,
                    'fund_code': fund.fund_code,
                    'fund_name': fund.fund_name,
                    'fund_type': fund.fund_type,
                    'net_asset_value': float(fund.net_asset_value) if fund.net_asset_value else 0.0,
                    'net_value_date': str(fund.net_value_date) if fund.net_value_date else None,
                    'fund_manager': fund.fund_manager,
                    'establish_date': str(fund.establish_date) if fund.establish_date else None,
                    'fund_size': float(fund.fund_size) if fund.fund_size else 0.0,
                    'remark': fund.remark,
                    'create_time': str(fund.create_time) if fund.create_time else None,
                    'update_time': str(fund.update_time) if fund.update_time else None
                })
            
            return result, total
        finally:
            session.close()

    def update_fund_remark(self, fund_code: str, remark: str) -> bool:
        session = self.get_session()
        try:
            fund = session.query(FundInfo).filter(
                FundInfo.fund_code == fund_code,
                FundInfo.del_flag == '1'
            ).first()
            
            if not fund:
                logger.warning(f"基金 {fund_code} 不存在，跳过更新")
                return False

            fund.remark = remark
            fund.update_time = get_beijing_now()
            fund.update_by = 'crawler'

            session.commit()
            logger.info(f"基金 {fund_code} remark 已更新: {remark}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"更新基金 {fund_code} remark 失败: {e}")
            return False
        finally:
            session.close()


