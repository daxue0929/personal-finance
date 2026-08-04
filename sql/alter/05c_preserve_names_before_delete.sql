-- ================================================
-- 5c/3 顺序正确版：先暂存 + 再 DELETE + 再 INSERT
-- 避免 4 行被删后 SELECT INTO 拿不到旧 task_name/cron
-- ================================================
SET NAMES utf8mb4;

-- 1. 先暂存 4 行旧 task_name / cron（在 DELETE 之前）
SELECT task_name, cron_expression INTO @kc50_tn, @kc50_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task'
   AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '000688'
   AND del_flag = '1' LIMIT 1;
SELECT task_name, cron_expression INTO @kc100_tn, @kc100_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task'
   AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '000698'
   AND del_flag = '1' LIMIT 1;
SELECT task_name, cron_expression INTO @hs300_tn, @hs300_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task'
   AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '000300'
   AND del_flag = '1' LIMIT 1;
SELECT task_name, cron_expression INTO @cyb50_tn, @cyb50_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task'
   AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '399673'
   AND del_flag = '1' LIMIT 1;

-- 2. 删 4 行 fetch_index_task
DELETE FROM task_schedule
 WHERE task_func = 'fetch_index_task' AND del_flag = '1';

-- 3. 插 4 行新 task_func
START TRANSACTION;
INSERT INTO task_schedule
  (task_name, task_func, cron_expression, enabled, description, func_args, del_flag, create_by, create_time, update_by, update_time)
VALUES
  (COALESCE(@kc50_tn,  '科创50指数抓取') ,  'fetch_index_task_000688', COALESCE(@kc50_cron,  '* 9-15 * * mon-fri'), 1, '科创50(000688) 每分钟抓取',  '{"index_code":"000688","market":"sh"}', '1', 'system_migration', NOW(), 'system_migration', NOW()),
  (COALESCE(@kc100_tn, '科创100指数抓取'),  'fetch_index_task_000698', COALESCE(@kc100_cron, '* 9-15 * * mon-fri'), 1, '科创100(000698) 每分钟抓取', '{"index_code":"000698","market":"sh"}', '1', 'system_migration', NOW(), 'system_migration', NOW()),
  (COALESCE(@hs300_tn, '沪深300指数抓取'),  'fetch_index_task_000300', COALESCE(@hs300_cron, '* 9-15 * * mon-fri'), 1, '沪深300(000300) 每分钟抓取', '{"index_code":"000300","market":"sh"}', '1', 'system_migration', NOW(), 'system_migration', NOW()),
  (COALESCE(@cyb50_tn, '创业板50指数抓取'), 'fetch_index_task_399673', COALESCE(@cyb50_cron, '* 9-15 * * mon-fri'), 1, '创业板50(399673) 每分钟抓取','{"index_code":"399673","market":"sz"}', '1', 'system_migration', NOW(), 'system_migration', NOW())
ON DUPLICATE KEY UPDATE
  cron_expression = VALUES(cron_expression),
  description     = VALUES(description),
  func_args       = VALUES(func_args),
  update_by       = 'system_migration',
  update_time     = NOW();
COMMIT;

-- ==================== 验证 ====================
-- SELECT task_func, task_name, JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) AS code, cron_expression
--   FROM task_schedule WHERE task_func LIKE 'fetch_index_task_%' AND del_flag = '1';
