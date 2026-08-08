SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 基金定投计划表
-- 存储基金的定投（定期定额买入）计划，一个基金可配多条规则（如每周三 + 每月10号）
-- 净值更新任务每30分钟跑，更新成功后检查启用中的定投计划，命中当天且当天有净值
-- （仅交易日）则自动插入一条当天 PENDING 买入流水，由 calculate_buyer_shares_task 计算份额
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `fund_dip_plan`;

CREATE TABLE `fund_dip_plan` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '定投计划ID（主键，自增）',
  `user_id` bigint NOT NULL DEFAULT '1' COMMENT '所属 user（多用户隔离）',
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
  KEY `idx_enable_dip` (`enable_dip`,`del_flag`) COMMENT '启用+删除标志复合索引（任务扫描用）',
  KEY `idx_user_id` (`user_id`) COMMENT 'user 索引（多用户隔离）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='基金定投计划表';

-- ================================================
-- 表说明：
-- 1. 一个基金可配多条定投计划（单基金多规则），如同时配「每周三」和「每月10号」
-- 2. enable_dip='1' 启用、'0' 停用；停用的计划净值更新任务不检查
-- 3. dip_mode 本期仅支持 fixed（固定金额=dip_amount），预留 smart（智能定投按涨跌幅系数）
-- 4. dip_frequency+dip_day 决定命中规则，匹配逻辑见 app.utils.dip_utils.should_dip_today
-- 5. 命中当天且当天能取到净值（仅交易日）才插 fund_buyer 流水，幂等由 fund_buyer.uk_fund_code_time 保证
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
