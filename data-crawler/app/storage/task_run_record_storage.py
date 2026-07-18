#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务执行记录数据存储层

每次任务执行（cron/手动）一条记录，含状态机 RUNNING/SUCCESS/FAILED/SKIPPED。
供前端「执行计划」弹窗查看历史；trace_id 关联 system_log 串联日志。
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Text

from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base, StorageBase


class TaskRunRecord(Base):
    __tablename__ = 'task_run_record'

    # BigInteger 在 MySQL 为 bigint AUTO_INCREMENT；with_variant(Integer) 让 sqlite 测试也能自增
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    task_func = Column(String(200), nullable=False)
    task_name = Column(String(100), default='')
    trigger_type = Column(String(20), nullable=False)  # cron / manual
    status = Column(String(20), nullable=False)  # RUNNING / SUCCESS / FAILED / SKIPPED
    trace_id = Column(String(64), default='')
    triggered_by = Column(String(64), default='')
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_ms = Column(Integer)
    error_message = Column(Text)
    create_time = Column(DateTime, default=get_beijing_now)
    update_time = Column(DateTime, default=get_beijing_now, onupdate=get_beijing_now)


class TaskRunRecordStorage(StorageBase):
    """任务执行记录存储层"""

    def __init__(self):
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def create_running_record(self, task_func: str, task_name: str, trigger_type: str,
                              trace_id: str, triggered_by: str) -> Optional[TaskRunRecord]:
        """新建 RUNNING 记录（任务开始时调用）"""
        session = self.get_session()
        try:
            now = get_beijing_now()
            record = TaskRunRecord(
                task_func=task_func,
                task_name=task_name,
                trigger_type=trigger_type,
                status='RUNNING',
                trace_id=trace_id,
                triggered_by=triggered_by,
                start_time=now,
                create_time=now,
                update_time=now
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"创建任务执行记录失败: {e}")
            return None
        finally:
            session.close()

    def create_skipped_record(self, task_func: str, task_name: str, trigger_type: str,
                              trace_id: str = '', triggered_by: str = '') -> Optional[TaskRunRecord]:
        """新建 SKIPPED 记录（cron 防重叠跳过时调用，start==end，duration=0）"""
        session = self.get_session()
        try:
            now = get_beijing_now()
            record = TaskRunRecord(
                task_func=task_func,
                task_name=task_name,
                trigger_type=trigger_type,
                status='SKIPPED',
                trace_id=trace_id,
                triggered_by=triggered_by,
                start_time=now,
                end_time=now,
                duration_ms=0,
                create_time=now,
                update_time=now
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except Exception as e:
            session.rollback()
            logger.error(f"创建跳过记录失败: {e}")
            return None
        finally:
            session.close()

    def update_record_status(self, record_id: int, status: str,
                             duration_ms: int = None, error_message: str = None) -> bool:
        """更新记录状态（任务结束时调用）：RUNNING -> SUCCESS/FAILED"""
        session = self.get_session()
        try:
            record = session.query(TaskRunRecord).filter(TaskRunRecord.id == record_id).first()
            if not record:
                logger.warning(f"任务执行记录 {record_id} 不存在")
                return False
            record.status = status
            record.end_time = get_beijing_now()
            if duration_ms is not None:
                record.duration_ms = duration_ms
            if error_message is not None:
                record.error_message = error_message
            record.update_time = get_beijing_now()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新任务执行记录状态失败: {e}")
            return False
        finally:
            session.close()

    def get_running_record_by_func(self, task_func: str) -> Optional[TaskRunRecord]:
        """查询某任务是否有 RUNNING 记录（防重叠检查用）"""
        session = self.get_session()
        try:
            return session.query(TaskRunRecord).filter(
                TaskRunRecord.task_func == task_func,
                TaskRunRecord.status == 'RUNNING'
            ).first()
        except Exception as e:
            logger.error(f"查询运行中任务记录失败: {e}")
            return None
        finally:
            session.close()

    def get_record_by_id(self, record_id: int) -> Optional[TaskRunRecord]:
        session = self.get_session()
        try:
            return session.query(TaskRunRecord).filter(TaskRunRecord.id == record_id).first()
        except Exception as e:
            logger.error(f"查询任务执行记录失败: {e}")
            return None
        finally:
            session.close()

    def get_records_with_pagination(self, task_func: str = None, status: str = None,
                                    page: int = 1, page_size: int = 20) -> Tuple[List[TaskRunRecord], int]:
        """分页查询执行记录（按 task_func/status 过滤，按开始时间倒序）"""
        session = self.get_session()
        try:
            q = session.query(TaskRunRecord)
            if task_func:
                q = q.filter(TaskRunRecord.task_func == task_func)
            if status:
                q = q.filter(TaskRunRecord.status == status)
            total = q.count()
            records = q.order_by(TaskRunRecord.start_time.desc(), TaskRunRecord.id.desc()) \
                       .offset((page - 1) * page_size).limit(page_size).all()
            return records, total
        except Exception as e:
            logger.error(f"分页查询任务执行记录失败: {e}")
            return [], 0
        finally:
            session.close()

    def clean_records_before(self, days: int) -> int:
        """清理 N 天前且非 RUNNING 的记录（RUNNING 不删，防误删在跑任务）。返回删除条数。"""
        session = self.get_session()
        try:
            threshold = get_beijing_now() - timedelta(days=days)
            deleted = session.query(TaskRunRecord).filter(
                TaskRunRecord.create_time < threshold,
                TaskRunRecord.status != 'RUNNING'
            ).delete(synchronize_session=False)
            session.commit()
            logger.info(f"清理 {days} 天前任务执行记录 {deleted} 条")
            return deleted
        except Exception as e:
            session.rollback()
            logger.error(f"清理任务执行记录失败: {e}")
            return 0
        finally:
            session.close()

    def get_running_task_funcs(self) -> List[str]:
        """查询所有当前 RUNNING 的 task_func（供任务列表接口标记 running 状态用）"""
        session = self.get_session()
        try:
            rows = session.query(TaskRunRecord.task_func).filter(
                TaskRunRecord.status == 'RUNNING'
            ).distinct().all()
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"查询运行中任务失败: {e}")
            return []
        finally:
            session.close()

    def reset_stale_running(self, threshold_minutes: int = 60) -> int:
        """将超时仍在 RUNNING 的记录置为 FAILED（进程崩溃/重启残留的僵尸记录）。

        启动时调用：本进程启动前残留的 RUNNING（start_time 早于 now - threshold）视为僵尸，
        置 FAILED + error_message。返回重置条数。阈值默认 60 分钟（长任务如 fundf10 抓取约 1 分钟，
        1 小时足够区分真在跑 vs 僵尸）。
        """
        session = self.get_session()
        try:
            threshold = get_beijing_now() - timedelta(minutes=threshold_minutes)
            records = session.query(TaskRunRecord).filter(
                TaskRunRecord.status == 'RUNNING',
                TaskRunRecord.start_time < threshold
            ).all()
            count = 0
            for r in records:
                r.status = 'FAILED'
                r.end_time = get_beijing_now()
                r.error_message = f'进程重启前未完成（启动时重置，原 start_time={r.start_time}）'
                r.update_time = get_beijing_now()
                count += 1
            session.commit()
            if count:
                logger.info(f"启动时重置 {count} 条僵尸 RUNNING 记录为 FAILED")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"重置僵尸 RUNNING 记录失败: {e}")
            return 0
        finally:
            session.close()

    def close(self):
        pass
