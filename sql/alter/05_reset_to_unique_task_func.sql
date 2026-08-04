-- ================================================
-- 5/3 撤销复合唯一索引，回 uk_task_func 唯一；改 task_func 为 fetch_index_task_<index_code>
-- 原因：4 行同 task_func='fetch_index_task' 时，APScheduler add_job 同 id 互相覆盖，
--      _resolve_func_args .first() 也不可预测返回哪行。
--      改为 4 个独立 task_func，调度器和 ORM 查询都按唯一字段定位。
-- ================================================
SET NAMES utf8mb4;

-- 1. 删复合唯一索引（如果存在）
ALTER TABLE task_schedule DROP INDEX uk_task_func_index;

-- 2. 加回简单 uk_task_func 唯一（如果不存在）
SET @idx_exists = (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE() AND table_name = 'task_schedule'
    AND index_name = 'uk_task_func'
);
SET @ddl = IF(@idx_exists = 0,
  'ALTER TABLE task_schedule ADD UNIQUE KEY uk_task_func (task_func)',
  'SELECT ''uk_task_func 已存在，跳过'' AS msg'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. 删除 4 行 fetch_index_task（之前迁移产生的）
DELETE FROM task_schedule
 WHERE task_func = 'fetch_index_task' AND del_flag = '1';

-- 4. 暂存 4 行旧 task_name/cron（从被删的 4 行取）
SELECT task_name, cron_expression INTO @kc50_tn, @kc50_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task' AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '000688' AND del_flag = '1' LIMIT 1;
SELECT task_name, cron_expression INTO @kc100_tn, @kc100_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task' AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '000698' AND del_flag = '1' LIMIT 1;
SELECT task_name, cron_expression INTO @hs300_tn, @hs300_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task' AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '000300' AND del_flag = '1' LIMIT 1;
SELECT task_name, cron_expression INTO @cyb50_tn, @cyb50_cron
  FROM task_schedule
 WHERE task_func = 'fetch_index_task' AND JSON_UNQUOTE(JSON_EXTRACT(func_args, '$.index_code')) = '399673' AND del_flag = '1' LIMIT 1;

-- 5. 插入 4 行新 task_func=fetch_index_task_<index_code>
--    func_args 也保留 index_code/market 便于人查（与 task_func 后缀冗余但无副作用）
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
-- 预期 4 行：fetch_index_task_000688 / _000698 / _000300 / _399673
