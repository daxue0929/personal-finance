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
import contextvars
from queue import Queue, Full

# 日志队列，用于异步写入数据库
_log_queue = Queue(maxsize=1000)
_log_queue_thread = None
_log_queue_running = False
_log_storage_instance = None

# ContextVar变量，用于传递日志上下文信息
trace_id_var = contextvars.ContextVar('trace_id', default='')
request_method_var = contextvars.ContextVar('request_method', default='')
request_path_var = contextvars.ContextVar('request_path', default='')
request_ip_var = contextvars.ContextVar('request_ip', default='')
category_var = contextvars.ContextVar('category', default='')
task_name_var = contextvars.ContextVar('task_name', default='')
storage_class_var = contextvars.ContextVar('storage_class', default='')
storage_method_var = contextvars.ContextVar('storage_method', default='')


def set_log_context(trace_id=None, request_method=None, request_path=None, 
                     request_ip=None, category=None, task_name=None,
                     storage_class=None, storage_method=None):
    """
    设置日志上下文（会覆盖已有值）
    用于在链路中间设置/覆盖上下文信息，如数据库层设置category='database'
    """
    tokens = []
    if trace_id is not None:
        tokens.append(trace_id_var.set(trace_id))
    if request_method is not None:
        tokens.append(request_method_var.set(request_method))
    if request_path is not None:
        tokens.append(request_path_var.set(request_path))
    if request_ip is not None:
        tokens.append(request_ip_var.set(request_ip))
    if category is not None:
        tokens.append(category_var.set(category))
    if task_name is not None:
        tokens.append(task_name_var.set(task_name))
    if storage_class is not None:
        tokens.append(storage_class_var.set(storage_class))
    if storage_method is not None:
        tokens.append(storage_method_var.set(storage_method))
    return tokens


def reset_log_context(tokens):
    """重置日志上下文（用于撤销set_log_context的设置）"""
    for token in reversed(tokens):
        try:
            token.var.reset(token)
        except Exception:
            pass


class database_log_context:
    """
    数据库操作的日志上下文管理器
    在数据库操作期间临时设置category='database'，操作结束后恢复
    """
    def __init__(self, category='database'):
        self.category = category
        self.tokens = []
    
    def __enter__(self):
        self.tokens = set_log_context(category=self.category)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        reset_log_context(self.tokens)
        return False


class ContextVarFilter(logging.Filter):
    """日志过滤器，自动从ContextVar注入上下文信息到LogRecord"""
    
    def filter(self, record):
        """将ContextVar中的上下文信息注入到LogRecord
        如果record中已有值（中间层设置的），则保留，不覆盖
        """
        # 只在record中对应字段为空时才从ContextVar填充
        if not getattr(record, 'trace_id', ''):
            record.trace_id = trace_id_var.get()
        if not getattr(record, 'request_method', ''):
            record.request_method = request_method_var.get()
        if not getattr(record, 'request_path', ''):
            record.request_path = request_path_var.get()
        if not getattr(record, 'request_ip', ''):
            record.request_ip = request_ip_var.get()
        if not getattr(record, 'category', ''):
            record.category = category_var.get()
        if not getattr(record, 'task_name', ''):
            record.task_name = task_name_var.get()
        if not getattr(record, 'storage_class', ''):
            record.storage_class = storage_class_var.get()
        if not getattr(record, 'storage_method', ''):
            record.storage_method = storage_method_var.get()
        return True


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
                'storage_class': getattr(record, 'storage_class', ''),
                'storage_method': getattr(record, 'storage_method', ''),
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

# 创建ContextVar过滤器并添加到处理器
context_var_filter = ContextVarFilter()
console_handler.addFilter(context_var_filter)
db_handler.addFilter(context_var_filter)

# 创建主logger
logger = logging.getLogger('data-crawler')
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)
logger.addHandler(db_handler)

# 防止重复添加处理器
logger.propagate = False


class LogContext:
    """日志上下文管理器，用于设置trace_id等上下文信息（基于contextvars实现）"""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._tokens = []
    
    def __enter__(self):
        # 设置ContextVar上下文
        var_map = {
            'trace_id': trace_id_var,
            'request_method': request_method_var,
            'request_path': request_path_var,
            'request_ip': request_ip_var,
            'category': category_var,
            'task_name': task_name_var
        }
        
        for key, value in self.kwargs.items():
            if key in var_map and value:
                try:
                    token = var_map[key].set(value)
                    self._tokens.append(token)
                except Exception:
                    pass
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 清理ContextVar上下文
        for token in reversed(self._tokens):
            try:
                token.var.reset(token)
            except Exception:
                pass
        self._tokens = []
    
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