-- ================================================
-- 新增基金定投计划表（生产环境增量建表脚本）
-- struct/fund_dip_plan.sql 是 DROP+CREATE 破坏性脚本，仅用于全新建库；
-- 本脚本用 CREATE TABLE IF NOT EXISTS，可在已有数据的生产库安全执行。
-- 表结构与 struct/fund_dip_plan.sql 完全一致。
-- ================================================

CREATE TABLE IF NOT EXISTS `fund_dip_plan` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '定投计划ID（主键，自增）',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称（冗余）',
  `enable_dip` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '是否启用定投（1启用 0停用）',
  `dip_mode` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'fixed' COMMENT '定投模式（fixed固定金额，预留smart智能定投）',
  `dip_frequency` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '定投频率（daily每日/weekly每周/monthly每月）',
  `dip_day` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '定投日（weekly:1-7周一至周日 monthly:1-28 daily:空）',
  `dip_amount` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '定投金额（元）',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_fund_code` (`fund_code`) USING BTREE COMMENT '基金代码索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_fund_code_del` (`fund_code`,`del_flag`) COMMENT '基金代码+删除标志复合索引',
  KEY `idx_enable_dip` (`enable_dip`,`del_flag`) COMMENT '启用+删除标志复合索引（任务扫描用）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='基金定投计划表';
