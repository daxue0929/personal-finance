#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深300指数数据抓取任务
指数代码: 000300
交易时段每分钟执行，实时更新当天数据
"""

from .index_fetch_helper import fetch_and_store_index
from ..utils.logger import logger


def fetch_hs300_index_task(force_run: bool = False):
    logger.info("=" * 50)
    logger.info("开始执行沪深300指数数据抓取任务")
    fetch_and_store_index('000300', force_run)
