-- ================================================
-- 添加计算基金卖出金额任务配置
-- 每小时执行一次，查询待处理的卖出记录，按卖出当日净值计算卖出金额并扣减持仓
-- 与 calculate_buyer_shares_task（计算买入份额任务）对称
-- ================================================

-- 插入任务配置（如果不存在）
INSERT IGNORE INTO task_schedule (task_name, task_func, cron_expression, enabled, description, del_flag, create_by, create_time)
VALUES
('calculate_seller_amount_task', 'calculate_seller_amount_task', '0 * * * *', 1, '每小时执行一次，查询待处理的卖出记录，按卖出当日净值计算卖出金额与已实现盈亏，并扣减基金持仓（加权平均成本法）', '1', 'system', NOW());
