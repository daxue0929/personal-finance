-- ================================================
-- 2/3 删旧 uk_task_func 唯一索引
-- 原因：4 行同 task_func='fetch_index_task' 在仅 task_func 唯一索引下会被合并为 1 行
-- 二次执行会报 1091 index does not exist，请忽略
-- ================================================
SET NAMES utf8mb4;

ALTER TABLE task_schedule DROP INDEX uk_task_func;
