#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓每日快照备份任务

每日凌晨3点备份昨天所有有效持仓的快照，盈亏按当日 fund_info.net_asset_value 重算。
走应用层路径（可测试、可日志追踪）；存储过程 backup_position_daily_snapshot 为 DBA 手动运维的次要路径。
"""

from ..storage import PositionDailySnapshotStorage
from ..utils.logger import logger


def backup_position_snapshot_task(force_run: bool = False):
    """
    持仓每日快照备份任务

    Args:
        force_run: 强制运行参数（任务本身不需要时间检查，直接执行）
    """
    logger.info("=" * 50)
    logger.info("开始执行持仓每日快照备份任务")

    storage = PositionDailySnapshotStorage()

    try:
        # 默认备份昨天；force_run 时也按昨天备份（保持幂等）
        result = storage.backup_snapshots_app_layer()
        logger.info(f"持仓每日快照备份任务完成，成功备份 {result} 条记录")

    except Exception as e:
        logger.error(f"持仓每日快照备份任务异常: {e}")
