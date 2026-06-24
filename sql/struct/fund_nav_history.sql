SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 基金历史净值表
-- 存储基金的历史净值数据
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `fund_nav_history`;

CREATE TABLE `fund_nav_history` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称',
  `nav_date` date NOT NULL COMMENT '净值日期',
  `unit_nav` decimal(8,4) DEFAULT NULL COMMENT '单位净值',
  `daily_growth_rate` decimal(8,4) DEFAULT NULL COMMENT '日涨跌幅(%)',
  `source` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'manual' COMMENT '数据来源（manual手动/crawler爬虫）',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `idx_fund_code_nav_date` (`fund_code`,`nav_date`) USING BTREE COMMENT '基金代码+净值日期唯一索引',
  KEY `idx_fund_code` (`fund_code`) USING BTREE COMMENT '基金代码索引',
  KEY `idx_nav_date` (`nav_date`) USING BTREE COMMENT '净值日期索引',
  KEY `idx_fund_date` (`fund_code`,`nav_date`) COMMENT '基金代码+净值日期复合索引',
  KEY `idx_create_time` (`create_time`) COMMENT '创建时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='基金历史净值表';

-- ================================================
-- 表说明：
-- 1. 存储基金的每日净值数据
-- 2. 同一基金同一日期只能有一条记录（通过唯一索引保证）
-- 3. source字段标识数据来源：manual-手动录入，crawler-爬虫抓取
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
