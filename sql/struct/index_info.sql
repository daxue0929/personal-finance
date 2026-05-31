SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for index_info
-- ----------------------------
DROP TABLE IF EXISTS `index_info`;
CREATE TABLE `index_info` (
  `index_id` bigint NOT NULL AUTO_INCREMENT COMMENT '指数ID',
  `index_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '指数代码',
  `index_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '指数名称',
  `index_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '宽基指数' COMMENT '指数类型（宽基指数/行业指数/策略指数）',
  `trade_date` date NOT NULL COMMENT '交易日期',
  `open_price` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '开盘价',
  `close_price` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '收盘价',
  `high_price` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '最高价',
  `low_price` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '最低价',
  `change_percent` decimal(6, 2) NULL DEFAULT 0.00 COMMENT '涨跌幅（%，基于前一日收盘价计算）',
  `volume` bigint NULL DEFAULT 0 COMMENT '成交量',
  `amount` decimal(20, 2) NULL DEFAULT 0.00 COMMENT '成交额（元）',
  `turnover_rate` decimal(6, 2) NULL DEFAULT 0.00 COMMENT '换手率（%）',
  `pe_ratio` decimal(8, 2) NULL DEFAULT 0.00 COMMENT '市盈率TTM（滚动市盈率）',
  `pe_percentile` decimal(5, 2) NULL DEFAULT 0.00 COMMENT 'PE分位（%，历史分位）',
  `pb_ratio` decimal(8, 2) NULL DEFAULT 0.00 COMMENT '市净率',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '创建者',
  `create_time` datetime NULL DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '更新者',
  `update_time` datetime NULL DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`index_id`) USING BTREE,
  UNIQUE INDEX `idx_index_code_date`(`index_code` ASC, `trade_date` ASC) USING BTREE,
  INDEX `idx_trade_date`(`trade_date` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '指数信息表' ROW_FORMAT = DYNAMIC;

SET FOREIGN_KEY_CHECKS = 1;
