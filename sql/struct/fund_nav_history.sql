SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fund_nav_history
-- ----------------------------
DROP TABLE IF EXISTS `fund_nav_history`;
CREATE TABLE `fund_nav_history` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT '基金名称',
  `nav_date` date NOT NULL COMMENT '净值日期',
  `unit_nav` decimal(8, 4) NULL DEFAULT NULL COMMENT '单位净值',
  `daily_growth_rate` decimal(8, 4) NULL DEFAULT NULL COMMENT '日涨跌幅(%)',
  `source` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'manual' COMMENT '数据来源（manual手动/crawler爬虫）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `idx_fund_code_nav_date` (`fund_code`, `nav_date`) USING BTREE COMMENT '基金代码+净值日期唯一索引',
  INDEX `idx_fund_code` (`fund_code`) USING BTREE,
  INDEX `idx_nav_date` (`nav_date`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '基金历史净值表' ROW_FORMAT = DYNAMIC;

SET FOREIGN_KEY_CHECKS = 1;
