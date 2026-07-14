-- ================================================
-- 添加持仓每日快照备份任务配置
-- 每日凌晨3点备份昨天所有有效持仓的快照（与基金净值历史备份同时段）
-- ================================================

INSERT IGNORE INTO task_schedule (task_name, task_func, cron_expression, enabled, description, del_flag, create_by, create_time)
VALUES
('backup_position_snapshot_task', 'backup_position_snapshot_task', '0 3 * * *', 1, '每日凌晨3点备份昨天所有有效持仓的快照，盈亏按当日净值重算，供持仓分析使用', '1', 'system', NOW());
