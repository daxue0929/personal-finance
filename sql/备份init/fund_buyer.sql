
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fund_buyer
-- ----------------------------
DROP TABLE IF EXISTS `fund_buyer`;
CREATE TABLE `fund_buyer`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '买入流水号标识',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '基金名称',
  `time` date NOT NULL DEFAULT (curdate()) COMMENT '买入日期',
  `amt` decimal(7, 4) NULL DEFAULT 0.0000 COMMENT '买入金额',
  `type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '买入类型, 1: 手工买入, 2: 定投买入',
  `policy` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '适用策略脚本, 用于计算买入价格',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '创建者',
  `create_time` datetime NULL DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '更新者',
  `update_time` datetime NULL DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备注',
  `buy_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'PENDING' COMMENT '定投状态: PENDING-未执行, SUCCESS-已成功, FAILED-执行失败',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_fund_code_time`(`fund_code` ASC, `time` ASC) USING BTREE,
  INDEX `idx_fund_code`(`fund_code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 14 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '基金买入流水表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of fund_buyer
-- ----------------------------
INSERT INTO `fund_buyer` VALUES (1, '020292', '华夏科创100ETF联结C', '2026-05-13', 100.0000, '1', '涨跌幅系数策略', '1', 'daxue', '2026-05-13 10:51:13', 'daxue', '2026-05-13 02:51:13', '涨跌幅=0.00%, 系数=1.0000', 'SUCCESS');
INSERT INTO `fund_buyer` VALUES (9, '020292', '华夏科创100ETF联结C', '2026-05-15', 100.0000, '1', '涨跌幅系数策略', '1', 'daxue', '2026-05-15 13:25:42', 'daxue', '2026-05-15 14:34:22', '涨跌幅=-2.16%, 系数=1.0000', 'SUCCESS');
INSERT INTO `fund_buyer` VALUES (11, '020292', '华夏科创100ETF联结C', '2026-05-18', 100.0000, '1', '涨跌幅系数策略', '1', 'daxue', '2026-05-18 15:01:12', 'daxue', '2026-05-18 14:59:12', '涨跌幅=-0.71%, 系数=1.0000', 'SUCCESS');
INSERT INTO `fund_buyer` VALUES (12, '020292', '华夏科创100ETF联结C', '2026-05-19', 100.0000, '1', '涨跌幅系数策略', '1', 'daxue', '2026-05-19 11:56:05', 'daxue', '2026-05-19 11:56:05', '涨跌幅=-0.51%, 系数=1.0000', 'SUCCESS');
INSERT INTO `fund_buyer` VALUES (13, '020292', '华夏科创100ETF联结C', '2026-05-20', 90.0000, '1', '涨跌幅系数策略', '1', 'daxue', '2026-05-20 14:29:13', 'daxue', '2026-05-20 14:29:13', '涨跌幅=3.42%, 系数=0.9000', 'PENDING');

SET FOREIGN_KEY_CHECKS = 1;
