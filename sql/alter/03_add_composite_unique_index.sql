-- ================================================
-- 3/3 加复合唯一索引
-- 依赖：MySQL 8.0+
-- 二次执行会报 1061 Duplicate key name 'uk_task_func_index'，请忽略
-- 注：必须 JSON_UNQUOTE 去掉 JSON 字符串的引号，否则 CAST AS CHAR(6) 截断报错
--     JSON_EXTRACT 返回带引号的字符串 "000688"（8 字符），
--     JSON_UNQUOTE 后才是纯字符串 000688（6 字符）
-- ================================================
SET NAMES utf8mb4;

-- 删旧索引（如果之前报错建了残骸）
ALTER TABLE task_schedule DROP INDEX uk_task_func_index;

-- 加正确的复合唯一索引
ALTER TABLE task_schedule ADD UNIQUE KEY uk_task_func_index
  (task_func, (CAST(JSON_UNQUOTE(func_args->'$.index_code') AS CHAR(6))));
