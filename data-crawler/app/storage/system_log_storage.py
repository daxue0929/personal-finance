#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统日志数据存储层
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, BigInteger, String, Text, DateTime
from sqlalchemy.orm import sessionmaker

from ..utils.db import get_db_session, get_db_engine
from ..utils.logger import logger
from ..utils.datetime_utils import get_beijing_now
from .base import Base


class SystemLog(Base):
    __tablename__ = 'system_log'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    level = Column(String(20), nullable=False)
    category = Column(String(50), default='')
    message = Column(Text, nullable=False)
    trace_id = Column(String(32), default='')
    request_method = Column(String(10), default='')
    request_path = Column(String(255), default='')
    request_ip = Column(String(45), default='')
    task_name = Column(String(100), default='')
    error_stack = Column(Text, default='')
    create_time = Column(DateTime)


class SystemLogStorage:
    """系统日志数据存储层"""

    def __init__(self):
        self.engine = get_db_engine()
        self.Session = get_db_session

    def get_session(self):
        """获取数据库会话"""
        return self.Session()

    def create_log(self, data: Dict[str, Any]) -> bool:
        """创建日志记录"""
        session = self.get_session()
        try:
            new_log = SystemLog(
                level=data.get('level', 'INFO'),
                category=data.get('category', ''),
                message=data.get('message', ''),
                trace_id=data.get('trace_id', ''),
                request_method=data.get('request_method', ''),
                request_path=data.get('request_path', ''),
                request_ip=data.get('request_ip', ''),
                task_name=data.get('task_name', ''),
                error_stack=data.get('error_stack', ''),
                create_time=data.get('create_time', get_beijing_now())
            )
            session.add(new_log)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"写入系统日志失败: {e}")
            return False
        finally:
            session.close()

    def batch_create_logs(self, logs_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """批量创建日志记录"""
        session = self.get_session()
        success_count = 0
        fail_count = 0
        try:
            for data in logs_data:
                try:
                    new_log = SystemLog(
                        level=data.get('level', 'INFO'),
                        category=data.get('category', ''),
                        message=data.get('message', ''),
                        trace_id=data.get('trace_id', ''),
                        request_method=data.get('request_method', ''),
                        request_path=data.get('request_path', ''),
                        request_ip=data.get('request_ip', ''),
                        task_name=data.get('task_name', ''),
                        error_stack=data.get('error_stack', ''),
                        create_time=data.get('create_time', get_beijing_now())
                    )
                    session.add(new_log)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    logger.error(f"写入单条日志失败: {e}")
            
            session.commit()
            return {'success': success_count, 'failed': fail_count}
        except Exception as e:
            session.rollback()
            logger.error(f"批量写入系统日志失败: {e}")
            return {'success': success_count, 'failed': fail_count + (len(logs_data) - success_count - fail_count)}
        finally:
            session.close()

    def get_logs_with_pagination(self, level=None, category=None, trace_id=None,
                                  request_path=None, task_name=None, start_time=None,
                                  end_time=None, page=1, page_size=20):
        """
        获取日志列表（支持搜索和分页）
        """
        session = self.get_session()
        try:
            query = session.query(SystemLog).order_by(SystemLog.create_time.desc())
            
            if level:
                query = query.filter(SystemLog.level == level)
            if category:
                query = query.filter(SystemLog.category == category)
            if trace_id:
                query = query.filter(SystemLog.trace_id == trace_id)
            if request_path:
                query = query.filter(SystemLog.request_path.like(f'%{request_path}%'))
            if task_name:
                query = query.filter(SystemLog.task_name.like(f'%{task_name}%'))
            if start_time:
                query = query.filter(SystemLog.create_time >= start_time)
            if end_time:
                query = query.filter(SystemLog.create_time <= end_time)
            
            total = query.count()
            
            logs = query.offset((page - 1) * page_size).limit(page_size).all()
            
            result = []
            for log in logs:
                result.append({
                    'id': log.id,
                    'level': log.level,
                    'category': log.category,
                    'message': log.message,
                    'trace_id': log.trace_id,
                    'request_method': log.request_method,
                    'request_path': log.request_path,
                    'request_ip': log.request_ip,
                    'task_name': log.task_name,
                    'error_stack': log.error_stack,
                    'create_time': str(log.create_time) if log.create_time else None
                })
            
            return result, total
        finally:
            session.close()

    def get_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取日志详情"""
        session = self.get_session()
        try:
            log = session.query(SystemLog).filter(SystemLog.id == log_id).first()
            if log:
                return {
                    'id': log.id,
                    'level': log.level,
                    'category': log.category,
                    'message': log.message,
                    'trace_id': log.trace_id,
                    'request_method': log.request_method,
                    'request_path': log.request_path,
                    'request_ip': log.request_ip,
                    'task_name': log.task_name,
                    'error_stack': log.error_stack,
                    'create_time': str(log.create_time) if log.create_time else None
                }
            return None
        finally:
            session.close()

    def delete_log(self, log_id: int) -> bool:
        """删除日志记录"""
        session = self.get_session()
        try:
            log = session.query(SystemLog).filter(SystemLog.id == log_id).first()
            if not log:
                return False
            
            session.delete(log)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除日志失败: {e}")
            return False
        finally:
            session.close()

    def delete_logs_by_time(self, before_time: datetime) -> int:
        """删除指定时间之前的日志"""
        session = self.get_session()
        try:
            count = session.query(SystemLog).filter(SystemLog.create_time < before_time).delete()
            session.commit()
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"按时间删除日志失败: {e}")
            return 0
        finally:
            session.close()