#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务调度数据存储层
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, BigInteger, String, Integer, DateTime, CHAR, Text

from ..utils.config import get_db_url
from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base


class TaskSchedule(Base):
    __tablename__ = 'task_schedule'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)
    task_func = Column(String(200), nullable=False, unique=True)
    cron_expression = Column(String(100), nullable=False)
    enabled = Column(Integer, default=1)
    description = Column(Text)
    del_flag = Column(CHAR(1), default='1')
    create_by = Column(String(64))
    create_time = Column(DateTime)
    update_by = Column(String(64))
    update_time = Column(DateTime)


class TaskScheduleStorage:
    """任务调度数据存储层"""

    def __init__(self):
        # 使用全局数据库管理器
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def get_all_enabled_tasks(self) -> List[TaskSchedule]:
        session = self.get_session()
        try:
            return session.query(TaskSchedule).filter(
                TaskSchedule.del_flag == '1',
                TaskSchedule.enabled == 1
            ).all()
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return []
        finally:
            session.close()

    def get_all_tasks(self) -> List[TaskSchedule]:
        session = self.get_session()
        try:
            return session.query(TaskSchedule).filter(
                TaskSchedule.del_flag == '1'
            ).all()
        except Exception as e:
            logger.error(f"获取所有任务列表失败: {e}")
            return []
        finally:
            session.close()

    def get_task_by_id(self, task_id: int) -> Optional[TaskSchedule]:
        session = self.get_session()
        try:
            return session.query(TaskSchedule).filter(
                TaskSchedule.id == task_id,
                TaskSchedule.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return None
        finally:
            session.close()

    def get_task_by_func(self, task_func: str) -> Optional[TaskSchedule]:
        session = self.get_session()
        try:
            return session.query(TaskSchedule).filter(
                TaskSchedule.task_func == task_func,
                TaskSchedule.del_flag == '1'
            ).first()
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return None
        finally:
            session.close()

    def create_task(self, task_name: str, task_func: str, cron_expression: str,
                   enabled: int = 1, description: str = None, create_by: str = 'system') -> Optional[TaskSchedule]:
        session = self.get_session()
        try:
            new_task = TaskSchedule(
                task_name=task_name,
                task_func=task_func,
                cron_expression=cron_expression,
                enabled=enabled,
                description=description,
                create_by=create_by,
                create_time=get_beijing_now(),
                update_by=create_by,
                update_time=get_beijing_now()
            )
            session.add(new_task)
            session.commit()
            session.refresh(new_task)
            return new_task
        except Exception as e:
            session.rollback()
            logger.error(f"创建任务失败: {e}")
            return None
        finally:
            session.close()

    def update_task(self, task_id: int, **kwargs) -> bool:
        session = self.get_session()
        try:
            task = session.query(TaskSchedule).filter(
                TaskSchedule.id == task_id,
                TaskSchedule.del_flag == '1'
            ).first()

            if not task:
                logger.warning(f"任务 {task_id} 不存在")
                return False

            for key, value in kwargs.items():
                if hasattr(task, key) and key not in ['id', 'create_time']:
                    setattr(task, key, value)

            task.update_time = get_beijing_now()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新任务失败: {e}")
            return False
        finally:
            session.close()

    def delete_task(self, task_id: int, update_by: str = 'system') -> bool:
        session = self.get_session()
        try:
            task = session.query(TaskSchedule).filter(
                TaskSchedule.id == task_id,
                TaskSchedule.del_flag == '1'
            ).first()

            if not task:
                logger.warning(f"任务 {task_id} 不存在")
                return False

            task.del_flag = '0'
            task.update_by = update_by
            task.update_time = get_beijing_now()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除任务失败: {e}")
            return False
        finally:
            session.close()

    def task_exists(self, task_func: str) -> bool:
        session = self.get_session()
        try:
            return session.query(TaskSchedule).filter(
                TaskSchedule.task_func == task_func,
                TaskSchedule.del_flag == '1'
            ).first() is not None
        except Exception as e:
            logger.error(f"检查任务是否存在失败: {e}")
            return False
        finally:
            session.close()

    def update_task_cron(self, task_func: str, cron_expression: str, update_by: str = 'system') -> bool:
        session = self.get_session()
        try:
            task = session.query(TaskSchedule).filter(
                TaskSchedule.task_func == task_func,
                TaskSchedule.del_flag == '1'
            ).first()

            if not task:
                logger.warning(f"任务 {task_func} 不存在")
                return False

            task.cron_expression = cron_expression
            task.update_by = update_by
            task.update_time = datetime.now()

            session.commit()
            logger.info(f"任务 {task_func} cron 表达式已更新为 {cron_expression}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"更新任务 cron 表达式失败: {e}")
            return False
        finally:
            session.close()

    def close(self):
        if self._engine:
            self._engine.dispose()
