SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 持仓组合表
-- 存储用户创建的投资组合信息
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `portfolio`;

CREATE TABLE `portfolio` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '组合ID（主键，自增）',
  `name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '组合名称',
  `description` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '组合描述',
  `total_value` decimal(15,2) DEFAULT '0.00' COMMENT '组合总市值',
  `total_cost` decimal(15,2) DEFAULT '0.00' COMMENT '组合总成本',
  `total_profit_loss` decimal(15,2) DEFAULT '0.00' COMMENT '组合总盈亏',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_name_del` (`name`,`del_flag`) COMMENT '组合名称+删除标志复合索引',
  KEY `idx_create_time` (`create_time`) COMMENT '创建时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='持仓组合表';

-- ================================================
-- 表说明：
-- 1. 每个用户可以创建多个投资组合
-- 2. 组合总市值、总成本、总盈亏由系统定期计算更新
-- 3. del_flag用于软删除，1表示正常，0表示已删除
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
