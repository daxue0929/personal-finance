#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLAlchemy 共享 Base 类和 Storage 基类
所有数据库模型都应该从这里导入 Base
所有 Storage 类都应该继承自 StorageBase 以自动获得日志上下文支持
"""

import inspect
import functools
from sqlalchemy.orm import declarative_base
from ..utils.logger import (
    set_log_context, reset_log_context,
    category_var, storage_class_var, storage_method_var, logger
)

Base = declarative_base()


def storage_log(func):
    """
    存储类方法日志装饰器
    自动设置category='database'，并携带类名和方法名
    对数据库 OperationalError（连接超时/断连）重试一次，规避远程库偶发网络抖动
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        from sqlalchemy.exc import OperationalError

        class_name = self.__class__.__name__
        method_name = func.__name__

        tokens = set_log_context(
            category='database',
            storage_class=class_name,
            storage_method=method_name
        )

        try:
            try:
                return func(self, *args, **kwargs)
            except OperationalError as e:
                # 连接级错误（2006/2003/2013 等）：连接池会自愈，重试一次
                code = e.orig.args[0] if e.orig else '?'
                logger.warning(f"数据库操作 {class_name}.{method_name} 失败(码{code})，重试一次")
                return func(self, *args, **kwargs)
        finally:
            reset_log_context(tokens)

    return wrapper


class StorageBase:
    """
    Storage 基类
    使用 __init_subclass__ 自动为所有子类的公共方法添加 @storage_log 装饰器
    公共方法定义：不以下划线开头的实例方法（排除特殊方法如 __init__, __str__ 等）
    """
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            if name.startswith('_'):
                continue
            
            original_method = getattr(method, '__wrapped__', method)
            
            if 'self' in inspect.signature(original_method).parameters:
                setattr(cls, name, storage_log(method))
