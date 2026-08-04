-- ================================================
-- 4/3 迁移 4 行旧 fetch_*_index_task 任务到 fetch_index_task
-- 事务：DELETE 旧 4 行 + INSERT 4 行新 func_args 化
-- 二次执行幂等：ON DUPLICATE KEY UPDATE 命中后只更新 func_args/update_time
-- ================================================
SET NAMES utf8mb4;

START TRANSACTION;

-- 暂存旧行 cron/description（用于保留原调度节奏）
SELECT cron_expression, description INTO @kc50_cron,  @kc50_desc
  FROM task_schedule WHERE task_func = 'fetch_kc50_index_task'  AND del_flag = '1' LIMIT 1;
SELECT cron_expression, description INTO @kc100_cron, @kc100_desc
  FROM task_schedule WHERE task_func = 'fetch_kc100_index_task' AND del_flag = '1' LIMIT 1;
SELECT cron_expression, description INTO @hs300_cron, @hs300_desc
  FROM task_schedule WHERE task_func = 'fetch_hs300_index_task' AND del_flag = '1' LIMIT 1;
SELECT cron_expression, description INTO @cyb50_cron, @cyb50_desc
  FROM task_schedule WHERE task_func = 'fetch_cyb50_index_task' AND del_flag = '1' LIMIT 1;

-- 删除 4 行旧任务
DELETE FROM task_schedule
 WHERE task_func IN ('fetch_kc50_index_task','fetch_kc100_index_task','fetch_hs300_index_task','fetch_cyb50_index_task')
   AND del_flag = '1';

-- 插入 4 行新统一任务（COALESCE 兜底：旧行已删时用默认 cron 和 task_name）
INSERT INTO task_schedule
  (task_name, task_func, cron_expression, enabled, description, func_args, del_flag, create_by, create_time, update_by, update_time)
VALUES
  (COALESCE(@kc50_desc,  '科创50指数抓取') ,  'fetch_index_task', COALESCE(@kc50_cron,  '*/5 * * * *'), 1, @kc50_desc,  '{"index_code":"000688","market":"sh"}', '1', 'system_migration', NOW(), 'system_migration', NOW()),
  (COALESCE(@kc100_desc, '科创100指数抓取'),  'fetch_index_task', COALESCE(@kc100_cron, '*/5 * * * *'), 1, @kc100_desc, '{"index_code":"000698","market":"sh"}', '1', 'system_migration', NOW(), 'system_migration', NOW()),
  (COALESCE(@hs300_desc, '沪深300指数抓取'),  'fetch_index_task', COALESCE(@hs300_cron, '*/5 * * * *'), 1, @hs300_desc, '{"index_code":"000300","market":"sh"}', '1', 'system_migration', NOW(), 'system_migration', NOW()),
  (COALESCE(@cyb50_desc, '创业板50指数抓取'), 'fetch_index_task', COALESCE(@cyb50_cron, '*/5 * * * *'), 1, @cyb50_desc, '{"index_code":"399673","market":"sz"}', '1', 'system_migration', NOW(), 'system_migration', NOW())
ON DUPLICATE KEY UPDATE
  cron_expression = VALUES(cron_expression),
  description     = VALUES(description),
  func_args       = VALUES(func_args),
  update_by       = 'system_migration',
  update_time     = NOW();

COMMIT;

-- ==================== 验证 ====================
-- 建议执行后确认 4 行：
-- SELECT task_func, JSON_EXTRACT(func_args, '$.index_code') AS code, JSON_EXTRACT(func_args, '$.market') AS market, cron_expression
--   FROM task_schedule WHERE task_func = 'fetch_index_task' AND del_flag = '1';
-- 预期：000688/sh、000698/sh、000300/sh、399673/sz 各一行
