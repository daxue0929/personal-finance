#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金买入流水数据存储层
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
                    'remark': buyer.remark,
                    'create_time': str(buyer.create_time) if buyer.create_time else None,
                    'update_time': str(buyer.update_time) if buyer.update_time else None
                })
            
            return result, total
        finally:
            session.close()

