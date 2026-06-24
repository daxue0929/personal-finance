SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 基金信息表
-- 存储基金的基本信息
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `fund_info`;

CREATE TABLE `fund_info` (
  `fund_id` bigint NOT NULL AUTO_INCREMENT COMMENT '基金ID（主键，自增）',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称',
  `fund_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '混合型' COMMENT '基金类型',
  `net_asset_value` decimal(7,4) DEFAULT '0.0000' COMMENT '基金净值',
  `net_value_date` date DEFAULT NULL COMMENT '净值日期',
  `fund_manager` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金经理',
  `establish_date` date DEFAULT NULL COMMENT '成立日期',
  `fund_size` decimal(15,2) DEFAULT '0.00' COMMENT '基金规模（亿元）',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`fund_id`) USING BTREE,
  UNIQUE KEY `idx_fund_code` (`fund_code`) USING BTREE COMMENT '基金代码唯一索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_fund_code_del` (`fund_code`,`del_flag`) COMMENT '基金代码+删除标志复合索引',
  KEY `idx_fund_name_del` (`fund_name`,`del_flag`) COMMENT '基金名称+删除标志复合索引',
  KEY `idx_net_value_date` (`net_value_date`) COMMENT '净值日期索引',
  KEY `idx_fund_type` (`fund_type`) COMMENT '基金类型索引',
  KEY `idx_fund_code_date_del` (`fund_code`,`net_value_date`,`del_flag`) COMMENT '基金代码+净值日期+删除标志复合索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='基金信息表';

-- ================================================
-- 表说明：
-- 1. 存储基金的基本信息，包括代码、名称、类型、净值等
-- 2. 基金净值由爬虫定时更新
-- 3. 基金代码唯一，不允许重复
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
