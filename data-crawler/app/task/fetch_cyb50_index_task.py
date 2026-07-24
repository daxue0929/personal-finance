#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创业板50指数数据抓取任务
指数代码: 399673（深证，sz 前缀）
交易时段每分钟执行，实时更新当天数据
"""

from .index_fetch_helper import fetch_and_store_index
from ..utils.logger import logger


def fetch_cyb50_index_task(force_run: bool = False):
    logger.info("=" * 50)
    logger.info("开始执行创业板50指数数据抓取任务")
    fetch_and_store_index('399673', force_run)
