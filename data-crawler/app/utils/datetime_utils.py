#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日期时间工具模块 - 统一处理北京时间
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo



# 北京时间时区
BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')


def get_beijing_now() -> datetime:
    """
    获取当前北京时间（带时区信息）
    
    Returns:
        datetime: 当前北京时间，包含时区信息
    """
    return datetime.now(
        ZoneInfo('Asia/Shanghai'))


def get_beijing_date() -> datetime:
    """
    获取当前北京日期（日期部分）
    
    Returns:
        datetime: 当前北京时间的日期部分（时间为00:00:00）
    """
    return get_beijing_now().date()


def get_beijing_timestamp() -> float:
    """
    获取当前北京时间的时间戳（秒）
    
    Returns:
        float: 当前北京时间的Unix时间戳
    """
    return get_beijing_now().timestamp()


def get_beijing_now_str(format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    获取当前北京时间的字符串表示
    
    Args:
        format: 日期格式化字符串，默认为 '%Y-%m-%d %H:%M:%S'
    
    Returns:
        str: 格式化后的日期时间字符串
    """
    return get_beijing_now().strftime(format)


def datetime_to_beijing(dt: datetime) -> datetime:
    """
    将datetime对象转换为北京时间
    
    Args:
        dt: 输入的datetime对象
        
    Returns:
        datetime: 转换为北京时间后的datetime对象
    """
    if dt.tzinfo is None:
        # 假设输入是UTC时间
        return dt.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)


def timestamp_to_beijing(ts: float) -> datetime:
    """
    将时间戳转换为北京时间
    
    Args:
        ts: Unix时间戳（秒）
        
    Returns:
        datetime: 北京时间datetime对象
    """
    return datetime.fromtimestamp(ts, tz=BEIJING_TZ)


def timestamp_ms_to_beijing(ts_ms: float) -> datetime:
    """
    将毫秒时间戳转换为北京时间
    
    Args:
        ts_ms: Unix时间戳（毫秒）
        
    Returns:
        datetime: 北京时间datetime对象
    """
    return datetime.fromtimestamp(ts_ms / 1000, tz=BEIJING_TZ)


def timestamp_ms_to_date_str(ts_ms: float, format: str = '%Y-%m-%d') -> str:
    """
    将毫秒时间戳转换为日期字符串
    
    Args:
        ts_ms: Unix时间戳（毫秒）
        format: 日期格式化字符串，默认为 '%Y-%m-%d'
        
    Returns:
        str: 格式化后的日期字符串
    """
    return timestamp_ms_to_beijing(ts_ms).strftime(format)


def is_after_trading_hours() -> bool:
    """
    判断当前时间是否已过下午3点（交易结束时间）
    
    Returns:
        bool: True表示已过下午3点，False表示在交易时间内
    """
    now = get_beijing_now()
    return now.time() > datetime.strptime('15:00:00', '%H:%M:%S').time()


def format_datetime(dt: datetime, format: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    格式化datetime对象为字符串
    
    Args:
        dt: datetime对象
        format: 格式化字符串
        
    Returns:
        str: 格式化后的字符串
    """
    return dt.strftime(format)
