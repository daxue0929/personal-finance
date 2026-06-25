-- ================================================
-- 添加计算基金买入份额任务配置
-- ================================================

-- 插入任务配置（如果不存在）
INSERT IGNORE INTO task_schedule (task_name, task_func, cron_expression, enabled, description, del_flag, create_by, create_time)
VALUES 
('calculate_buyer_shares_task', 'calculate_buyer_shares_task', '0 * * * *', 1, '每小时执行一次，查询待处理的买入记录，根据净值计算份额', '1', 'system', NOW());
