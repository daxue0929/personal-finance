-- ================================================
-- index_info 表新增 source 字段（数据来源）
-- 记录指数数据从哪个网站/接口抓取（如"腾讯财经"），便于追溯数据来源
-- ================================================

ALTER TABLE `index_info`
  ADD COLUMN `source` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '腾讯财经' COMMENT '数据来源（抓取的网站/接口，如腾讯财经）' AFTER `pb_ratio`;
