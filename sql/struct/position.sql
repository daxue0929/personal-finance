SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for position
-- ----------------------------
DROP TABLE IF EXISTS `position`;
CREATE TABLE `position`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '持仓ID',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '基金名称',
  `shares` decimal(15, 4) NULL DEFAULT 0.0000 COMMENT '持仓份额',
  `cost_price` decimal(7, 4) NULL DEFAULT 0.0000 COMMENT '成本价（买入净值）',
  `current_price` decimal(7, 4) NULL DEFAULT 0.0000 COMMENT '当前净值',
  `current_value` decimal(15, 2) NULL DEFAULT 0.00 COMMENT '当前市值',
  `cost_amount` decimal(15, 2) NULL DEFAULT 0.00 COMMENT '成本金额',
  `profit_loss` decimal(15, 2) NULL DEFAULT 0.00 COMMENT '盈亏金额',
  `profit_loss_rate` decimal(6, 2) NULL DEFAULT 0.00 COMMENT '盈亏比例（%）',
  `buy_date` date NULL DEFAULT NULL COMMENT '买入日期',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '创建者',
  `create_time` datetime NULL DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '更新者',
  `update_time` datetime NULL DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_fund_code`(`fund_code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '持仓表' ROW_FORMAT = DYNAMIC;

SET FOREIGN_KEY_CHECKS = 1;