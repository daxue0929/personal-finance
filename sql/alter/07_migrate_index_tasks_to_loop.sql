-- ================================================
-- 迁移 4 条老 fetch_index_task_<code> 抓取任务 → 单条 fetch_all_indexes_task
-- 配套功能：PRD "index-basic-table" + tasks-index-basic-table §T1.3
--
-- 逻辑：
-- 1. 新增 1 条 fetch_all_indexes_task（遍历 index_basic.enabled=1 全量抓取）
-- 2. 禁用 4 条老 fetch_index_task_<code>（enabled: 1→0，保留记录便于回滚）
--
-- 二次执行幂等：
--   INSERT 用 ON DUPLICATE KEY UPDATE（命中后只更新元数据）
--   UPDATE WHERE enabled=1（只动在用的，不覆盖已禁用的）
--
-- 注意：8d939f2 重构后 4 条老任务的 task_func 是 fetch_index_task_000688/_000698/_000300/_399673
--       （不是字面的 fetch_index_task）—— 用 LIKE 'fetch_index_task_%' 匹配
-- ================================================

SET NAMES utf8mb4;

-- 暂存老任务 cron（保留原调度节奏；fetch_all_indexes_task 也用相同 cron 一次跑完所有指数）
SELECT cron_expression INTO @kc50_cron
  FROM task_schedule WHERE task_func = 'fetch_index_task_000688' AND del_flag = '1' LIMIT 1;
SELECT cron_expression INTO @kc100_cron
  FROM task_schedule WHERE task_func = 'fetch_index_task_000698' AND del_flag = '1' LIMIT 1;
SELECT cron_expression INTO @hs300_cron
  FROM task_schedule WHERE task_func = 'fetch_index_task_000300' AND del_flag = '1' LIMIT 1;
SELECT cron_expression INTO @cyb50_cron
  FROM task_schedule WHERE task_func = 'fetch_index_task_399673' AND del_flag = '1' LIMIT 1;

-- 新增 1 条统一抓取任务（COALESCE 兜底：老 cron 不存在时用默认 0 9 * * 1-5）
-- ON DUPLICATE KEY UPDATE 二次执行幂等
INSERT INTO task_schedule
  (task_name, task_func, cron_expression, enabled, description, del_flag, create_by, create_time, update_by, update_time)
VALUES
  ('统一指数抓取（全量遍历 index_basic）', 'fetch_all_indexes_task',
   COALESCE(@kc50_cron,  '0 9 * * 1-5'), 1,
   '遍历 index_basic.enabled=1 全量拉取；ThreadPool(4) 并发；kc100 副作用在 result 收集后单线程触发',
   '1', 'system_migration', NOW(), 'system_migration', NOW())
ON DUPLICATE KEY UPDATE
  task_name       = VALUES(task_name),
  cron_expression = VALUES(cron_expression),
  description     = VALUES(description),
  update_by       = 'system_migration',
  update_time     = NOW();

-- 禁用 4 条老任务（enabled: 1→0，保留记录；WHERE enabled=1 保证只动在用的，幂等）
UPDATE task_schedule
   SET enabled    = 0,
       update_by  = 'system_migration',
       update_time = NOW()
 WHERE task_func LIKE 'fetch_index_task_%'
   AND enabled = 1
   AND del_flag = '1';

-- ==================== 验证 ====================
-- 建议执行后确认 5 行：
-- SELECT task_func, COUNT(*) AS row_count, SUM(enabled) AS enabled_count
--   FROM task_schedule
--  WHERE task_func LIKE 'fetch_index_task_%' OR task_func = 'fetch_all_indexes_task'
--  GROUP BY task_func
--  ORDER BY task_func;
--
-- 预期：
--   fetch_all_indexes_task      1  1
--   fetch_index_task_000300     1  0
--   fetch_index_task_000688     1  0
--   fetch_index_task_000698     1  0
--   fetch_index_task_399673     1  0
--
-- ==================== 回滚 ====================
-- 如需回滚到老 4 条任务驱动：
--   UPDATE task_schedule SET enabled=1, update_by='rollback', update_time=NOW()
--    WHERE task_func LIKE 'fetch_index_task_%' AND del_flag='1';
--   UPDATE task_schedule SET enabled=0, update_by='rollback', update_time=NOW()
--    WHERE task_func='fetch_all_indexes_task' AND del_flag='1';
