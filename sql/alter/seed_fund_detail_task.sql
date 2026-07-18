-- ================================================
-- 添加基金详情网页抓取任务配置
-- 用 Playwright 抓取东方财富 fundf10 基本概况并打印结构化数据（骨架阶段不落库）
-- 默认禁用（enabled=0），仅前端任务页手动执行；启用后按 cron 每天3点跑
-- 对应代码：app/task/fetch_fund_detail_task.py（已注册到 register_task 的 task_registry）
-- ================================================

-- 插入任务配置（如果不存在）
INSERT IGNORE INTO task_schedule (task_name, task_func, cron_expression, enabled, description, del_flag, create_by, create_time, update_by, update_time)
VALUES
('基金详情网页抓取任务', 'fetch_fund_detail_task', '0 3 * * *', 0, '用 Playwright 抓取东方财富 fundf10 基本概况并打印结构化数据（骨架阶段不落库）。默认禁用，仅手动执行；启用后会按 cron 每天3点跑。', '1', 'system', NOW(), 'system', NOW());
