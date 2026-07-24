-- ================================================
-- position 表新增关联指数字段
-- 存储持仓关联的对标指数代码（如 000300 沪深300），选填
-- 仅存 index_code，指数名称展示时前端用 index_info 选项做 code->name 映射
-- ================================================

ALTER TABLE `position`
  ADD COLUMN `index_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '关联指数代码' AFTER `buy_date`;
