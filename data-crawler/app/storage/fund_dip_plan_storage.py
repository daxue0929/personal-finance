#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金定投计划数据存储层

存储基金的定投计划（一个基金可配多条规则）。净值更新任务通过 get_enabled_plans
取出启用中的计划，结合 app.utils.dip_utils.should_dip_today 判断当天是否命中，
命中则调用 FundBuyerStorage.create_buyer 插入一条当天 PENDING 买入流水。
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, BigInteger, String, Date, DateTime, DECIMAL, CHAR

from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


class FundDipPlan(Base):
    __tablename__ = 'fund_dip_plan'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, default=1, index=True, comment='所属 user（multi-user 隔离）')
    fund_code = Column(String(10), nullable=False)
    fund_name = Column(String(64), default='')
    enable_dip = Column(CHAR(1), default='1')
    dip_mode = Column(String(20), default='fixed')
    dip_frequency = Column(String(20), nullable=False)
    dip_day = Column(String(20), default='')
    dip_amount = Column(DECIMAL(10, 2), default=0.00)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64), default='')
    create_time = Column(DateTime)
    update_by = Column(String(64), default='')
    update_time = Column(DateTime)
    remark = Column(String(500))


class FundDipPlanStorage(StorageBase):
    """基金定投计划数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    @staticmethod
    def _to_dict(plan: FundDipPlan) -> Dict[str, Any]:
        return {
            'id': plan.id,
            'fund_code': plan.fund_code,
            'fund_name': plan.fund_name,
            'enable_dip': plan.enable_dip,
            'dip_mode': plan.dip_mode,
            'dip_frequency': plan.dip_frequency,
            'dip_day': plan.dip_day,
            'dip_amount': float(plan.dip_amount) if plan.dip_amount else 0.0,
            'remark': plan.remark,
            'create_time': str(plan.create_time) if plan.create_time else None,
            'update_time': str(plan.update_time) if plan.update_time else None,
        }

    def get_plans_by_fund_code(self, fund_code: str, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取指定基金的所有定投计划（含已停用，供前端管理）
        :param user_id: 限定 user；None = 不过滤
        """
        session = self.get_session()
        try:
            query = session.query(FundDipPlan).filter(
                FundDipPlan.fund_code == fund_code,
                FundDipPlan.del_flag == '1'
            )
            if user_id is not None:
                query = query.filter(FundDipPlan.user_id == user_id)
            plans = query.order_by(FundDipPlan.id.asc()).all()
            return [self._to_dict(p) for p in plans]
        except Exception as e:
            logger.error(f"获取基金 {fund_code} 定投计划失败: {e}")
            return []
        finally:
            session.close()

    def get_enabled_plans(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有启用中的定投计划（净值更新任务扫描用）
        :param user_id: 限定 user；None = 不过滤（admin/scheduler 跨用户视角）
        """
        session = self.get_session()
        try:
            query = session.query(FundDipPlan).filter(
                FundDipPlan.enable_dip == '1',
                FundDipPlan.del_flag == '1'
            )
            if user_id is not None:
                query = query.filter(FundDipPlan.user_id == user_id)
            plans = query.all()
            return [self._to_dict(p) for p in plans]
        except Exception as e:
            logger.error(f"获取启用定投计划失败: {e}")
            return []
        finally:
            session.close()

    def create_plan(self, data: Dict[str, Any]) -> Optional[int]:
        """创建定投计划

        :return: 新建计划 id，失败返回 None
        """
        session = self.get_session()
        try:
            new_plan = FundDipPlan(
                fund_code=data.get('fund_code', ''),
                fund_name=data.get('fund_name', ''),
                enable_dip=data.get('enable_dip', '1'),
                dip_mode=data.get('dip_mode', 'fixed'),
                dip_frequency=data.get('dip_frequency', ''),
                dip_day=data.get('dip_day', ''),
                dip_amount=data.get('dip_amount', 0.0),
                remark=data.get('remark', ''),
                del_flag='1',
                create_by=data.get('create_by', 'api'),
                create_time=get_beijing_now(),
                update_by=data.get('create_by', 'api'),
                update_time=get_beijing_now()
            )
            session.add(new_plan)
            session.commit()
            session.refresh(new_plan)
            logger.info(f"创建定投计划成功: id={new_plan.id}, 基金 {new_plan.fund_code}")
            return new_plan.id
        except Exception as e:
            session.rollback()
            logger.error(f"创建定投计划失败: {e}")
            return None
        finally:
            session.close()

    def update_plan(self, plan_id: int, data: Dict[str, Any]) -> bool:
        """更新定投计划"""
        session = self.get_session()
        try:
            plan = session.query(FundDipPlan).filter(
                FundDipPlan.id == plan_id,
                FundDipPlan.del_flag == '1'
            ).first()

            if not plan:
                logger.warning(f"定投计划 {plan_id} 不存在")
                return False

            if 'fund_name' in data:
                plan.fund_name = data['fund_name']
            if 'enable_dip' in data:
                plan.enable_dip = data['enable_dip']
            if 'dip_mode' in data:
                plan.dip_mode = data['dip_mode']
            if 'dip_frequency' in data:
                plan.dip_frequency = data['dip_frequency']
            if 'dip_day' in data:
                plan.dip_day = data['dip_day']
            if 'dip_amount' in data:
                plan.dip_amount = data['dip_amount']
            if 'remark' in data:
                plan.remark = data['remark']

            plan.update_by = 'api'
            plan.update_time = get_beijing_now()
            session.commit()
            logger.info(f"更新定投计划 {plan_id} 成功")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新定投计划 {plan_id} 失败: {e}")
            return False
        finally:
            session.close()

    def delete_plan(self, plan_id: int) -> bool:
        """软删除定投计划"""
        session = self.get_session()
        try:
            plan = session.query(FundDipPlan).filter(
                FundDipPlan.id == plan_id,
                FundDipPlan.del_flag == '1'
            ).first()

            if not plan:
                logger.warning(f"定投计划 {plan_id} 不存在")
                return False

            plan.del_flag = '0'
            plan.update_by = 'api'
            plan.update_time = get_beijing_now()
            session.commit()
            logger.info(f"删除定投计划 {plan_id} 成功")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除定投计划 {plan_id} 失败: {e}")
            return False
        finally:
            session.close()
