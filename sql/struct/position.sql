SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 持仓表
-- 存储用户持有的基金持仓信息
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `position`;

CREATE TABLE `position` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '持仓ID（主键，自增）',
  `user_id` bigint NOT NULL DEFAULT '1' COMMENT '所属 user（多用户隔离）',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称',
  `shares` decimal(15,4) DEFAULT '0.0000' COMMENT '持仓份额',
  `cost_price` decimal(7,4) DEFAULT '0.0000' COMMENT '成本价（买入净值）',
  `current_price` decimal(7,4) DEFAULT '0.0000' COMMENT '当前净值',
  `current_value` decimal(15,2) DEFAULT '0.00' COMMENT '当前市值',
  `cost_amount` decimal(15,2) DEFAULT '0.00' COMMENT '成本金额',
  `profit_loss` decimal(15,2) DEFAULT '0.00' COMMENT '盈亏金额',
  `profit_loss_rate` decimal(6,2) DEFAULT '0.00' COMMENT '盈亏比例（%）',
  `buy_date` date DEFAULT NULL COMMENT '买入日期',
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
  KEY `idx_fund_name_del` (`fund_name`,`del_flag`) COMMENT '基金名称+删除标志复合索引',
  KEY `idx_buy_date` (`buy_date`) COMMENT '买入日期索引',
  KEY `idx_current_value` (`current_value`) COMMENT '当前市值索引',
  KEY `idx_profit_loss` (`profit_loss`) COMMENT '盈亏金额索引',
  KEY `idx_buy_date_fund` (`buy_date`,`fund_code`) COMMENT '买入日期+基金代码复合索引',
  KEY `idx_user_id` (`user_id`) COMMENT 'user 索引（多用户隔离）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='持仓表';

-- ================================================
-- 表说明：
-- 1. 每条记录代表用户持有的一只基金
-- 2. 当前市值 = 持仓份额 * 当前净值
-- 3. 成本金额 = 持仓份额 * 成本价
-- 4. 盈亏金额 = 当前市值 - 成本金额
-- 5. 盈亏比例 = (当前市值 - 成本金额) / 成本金额 * 100%
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
