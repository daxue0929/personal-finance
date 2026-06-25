#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理模块
提供统一的日志记录功能，同时支持控制台输出和数据库存储
"""

import logging
import sys
import threading
import time
from queue import Queue, Full

# 日志队列，用于异步写入数据库
_log_queue = Queue(maxsize=1000)
_log_queue_thread = None
_log_queue_running = False
_log_storage_instance = None


class DatabaseLogHandler(logging.Handler):
    """自定义日志处理器，将日志写入数据库"""

    def __init__(self):
        super().__init__()
        self.storage = None

    def emit(self, record):
        """将日志记录发送到队列，异步处理"""
        try:
            # 过滤日志API本身的请求，避免冗余
            request_path = getattr(record, 'request_path', '')
            if request_path.startswith('/api/logs'):
                return
            
            # 创建日志数据
            log_data = {
                'level': record.levelname,
                'category': getattr(record, 'category', ''),
                'message': self.format(record),
                'trace_id': getattr(record, 'trace_id', ''),
                'request_method': getattr(record, 'request_method', ''),
                'request_path': getattr(record, 'request_path', ''),
                'request_ip': getattr(record, 'request_ip', ''),
                'task_name': getattr(record, 'task_name', ''),
                'error_stack': getattr(record, 'exc_text', '') if record.exc_info else '',
                'create_time': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 放入队列（非阻塞）
            try:
                _log_queue.put_nowait(log_data)
            except Full:
                # 队列满时丢弃最旧的日志
                try:
                    _log_queue.get_nowait()
                    _log_queue.put_nowait(log_data)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


def _process_log_queue():
    """后台线程：处理日志队列，写入数据库"""
    global _log_queue_running, _log_storage_instance
    
    while _log_queue_running:
        try:
            # 批量获取日志（最多100条，超时5秒）
            logs_data = []
            while len(logs_data) < 100:
                try:
                    log_data = _log_queue.get(timeout=5)
                    logs_data.append(log_data)
                except Exception:
                    break
            
            # 如果有日志需要写入
            if logs_data:
                try:
                    # 延迟导入避免循环依赖
                    from ..storage import SystemLogStorage
                    
                    if not _log_storage_instance:
                        _log_storage_instance = SystemLogStorage()
                    
                    result = _log_storage_instance.batch_create_logs(logs_data)
                    
                    if result.get('failed', 0) > 0:
                        logging.getLogger('data-crawler').warning(
                            f"批量写入日志失败: 成功{result['success']}条, 失败{result['failed']}条"
                        )
                except Exception as e:
                    # 数据库写入失败，记录到控制台
                    logging.getLogger('data-crawler').error(f"写入日志到数据库失败: {e}")
                    # 尝试重新放入队列
                    for log_data in logs_data:
                        try:
                            _log_queue.put_nowait(log_data)
                        except Full:
                            break
                    
                    # 等待一段时间后重试
                    time.sleep(1)
        except Exception:
            time.sleep(1)


def start_log_queue():
    """启动日志队列处理线程"""
    global _log_queue_running, _log_queue_thread
    
    if not _log_queue_running:
        _log_queue_running = True
        _log_queue_thread = threading.Thread(target=_process_log_queue, daemon=True)
        _log_queue_thread.start()


def stop_log_queue():
    """停止日志队列处理线程"""
    global _log_queue_running
    
    _log_queue_running = False
    
    if _log_queue_thread:
        _log_queue_thread.join(timeout=10)


# 创建格式化器
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# 创建数据库处理器（异步）
db_handler = DatabaseLogHandler()
db_handler.setLevel(logging.INFO)

# 创建主logger
logger = logging.getLogger('data-crawler')
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)
logger.addHandler(db_handler)

# 防止重复添加处理器
logger.propagate = False


class LogContext:
    """日志上下文管理器，用于设置trace_id等上下文信息"""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def debug(self, msg, **kwargs):
        extra = {**self.kwargs, **kwargs}
        logger.debug(msg, extra=extra)
    
    def info(self, msg, **kwargs):
        extra = {**self.kwargs, **kwargs}
        logger.info(msg, extra=extra)
    
    def warning(self, msg, **kwargs):
        extra = {**self.kwargs, **kwargs}
        logger.warning(msg, extra=extra)
    
    def error(self, msg, **kwargs):
        extra = {**self.kwargs, **kwargs}
        logger.error(msg, extra=extra)
    
    def critical(self, msg, **kwargs):
        extra = {**self.kwargs, **kwargs}
        logger.critical(msg, extra=extra)