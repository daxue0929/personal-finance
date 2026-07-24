#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科创50指数数据抓取任务
指数代码: 000688
每分钟执行一次，实时更新当天数据
"""

from .index_fetch_helper import fetch_and_store_index
from ..utils.logger import logger


def fetch_kc50_index_task(force_run: bool = False):
    logger.info("=" * 50)
    logger.info("开始执行科创50指数数据抓取任务")
    fetch_and_store_index('000688', force_run)
