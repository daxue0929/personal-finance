SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 基金买入流水表
-- 存储基金买入记录
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `fund_buyer`;

CREATE TABLE `fund_buyer` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '买入流水号标识（主键，自增）',
  `user_id` bigint NOT NULL DEFAULT '1' COMMENT '所属 user（多用户隔离）',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称',
  `time` date NOT NULL DEFAULT (curdate()) COMMENT '买入日期',
  `amt` decimal(7,4) DEFAULT '0.0000' COMMENT '买入金额',
  `type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '买入类型',
  `policy` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '适用策略脚本',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
  `buy_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'PENDING' COMMENT '买入状态（PENDING待处理/SUCCESS成功/FAILED失败）',
  `shares` decimal(15,4) DEFAULT NULL COMMENT '买入份额（日舍五入，保留两位小数）',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `uk_fund_code_time` (`fund_code`,`time`) USING BTREE COMMENT '基金代码+买入日期唯一索引',
  KEY `idx_fund_code` (`fund_code`) USING BTREE COMMENT '基金代码索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_fund_code_del` (`fund_code`,`del_flag`) COMMENT '基金代码+删除标志复合索引',
  KEY `idx_fund_name_del` (`fund_name`,`del_flag`) COMMENT '基金名称+删除标志复合索引',
  KEY `idx_time` (`time`) COMMENT '买入日期索引',
  KEY `idx_buy_status` (`buy_status`) COMMENT '买入状态索引',
  KEY `idx_time_status` (`time`,`buy_status`) COMMENT '买入日期+买入状态复合索引',
  KEY `idx_fund_time_status_del` (`fund_code`,`time`,`buy_status`,`del_flag`) COMMENT '基金代码+买入日期+买入状态+删除标志复合索引',
  KEY `idx_user_id` (`user_id`) COMMENT 'user 索引（多用户隔离）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='基金买入流水表';

-- ================================================
-- 表说明：
-- 1. 存储基金买入记录，支持手动录入和自动策略买入
-- 2. 同一基金同一天只能买入一次（通过唯一索引保证）
-- 3. buy_status字段表示买入状态：PENDING-待处理，SUCCESS-成功，FAILED-失败
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
