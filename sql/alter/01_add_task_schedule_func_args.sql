-- ================================================
-- 1/3 加 func_args 列
-- 依赖：MySQL 8.0+（JSON 列）
-- 二次执行会报 1060 Duplicate column 'func_args'，请忽略
-- ================================================
SET NAMES utf8mb4;

ALTER TABLE task_schedule
  ADD COLUMN func_args JSON NULL
  COMMENT '任务函数参数(JSON)' AFTER description;
