SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for portfolio_position
-- ----------------------------
DROP TABLE IF EXISTS `portfolio_position`;
CREATE TABLE `portfolio_position`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关联ID',
  `portfolio_id` bigint NOT NULL COMMENT '组合ID',
  `position_id` bigint NOT NULL COMMENT '持仓ID',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '创建者',
  `create_time` datetime NULL DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '更新者',
  `update_time` datetime NULL DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_portfolio_position`(`portfolio_id` ASC, `position_id` ASC) USING BTREE,
  INDEX `idx_portfolio_id`(`portfolio_id` ASC) USING BTREE,
  INDEX `idx_position_id`(`position_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '持仓组合和持仓关联表' ROW_FORMAT = DYNAMIC;

SET FOREIGN_KEY_CHECKS = 1;