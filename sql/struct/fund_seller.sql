SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 基金卖出流水表
-- 存储基金卖出（赎回）记录，与 fund_buyer 镜像对称
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `fund_seller`;

CREATE TABLE `fund_seller` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '卖出流水号标识（主键，自增）',
  `user_id` bigint NOT NULL DEFAULT '1' COMMENT '所属 user（多用户隔离）',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称',
  `time` date NOT NULL DEFAULT (curdate()) COMMENT '卖出日期',
  `shares` decimal(15,4) NOT NULL DEFAULT '0.0000' COMMENT '卖出份额（手动录入，必填）',
  `amt` decimal(15,4) DEFAULT NULL COMMENT '卖出金额（任务计算：份额×当日净值，初始为空）',
  `nav` decimal(7,4) DEFAULT NULL COMMENT '卖出所用净值（任务回写，审计用）',
  `realized_profit` decimal(15,2) DEFAULT NULL COMMENT '已实现盈亏（任务计算：(卖出净值-成本价)×份额）',
  `type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '卖出类型（1手动卖出 2止盈卖出 3止损卖出）',
  `policy` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '适用策略脚本',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
  `sell_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'PENDING' COMMENT '卖出状态（PENDING待处理/SUCCESS成功/FAILED失败）',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `uk_fund_code_time` (`fund_code`,`time`) USING BTREE COMMENT '基金代码+卖出日期唯一索引',
  KEY `idx_fund_code` (`fund_code`) USING BTREE COMMENT '基金代码索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_fund_code_del` (`fund_code`,`del_flag`) COMMENT '基金代码+删除标志复合索引',
  KEY `idx_fund_name_del` (`fund_name`,`del_flag`) COMMENT '基金名称+删除标志复合索引',
  KEY `idx_time` (`time`) COMMENT '卖出日期索引',
  KEY `idx_sell_status` (`sell_status`) COMMENT '卖出状态索引',
  KEY `idx_time_status` (`time`,`sell_status`) COMMENT '卖出日期+卖出状态复合索引',
  KEY `idx_fund_time_status_del` (`fund_code`,`time`,`sell_status`,`del_flag`) COMMENT '基金代码+卖出日期+卖出状态+删除标志复合索引',
  KEY `idx_status_shares` (`sell_status`,`shares`) COMMENT '卖出状态+份额复合索引（任务用）',
  KEY `idx_user_id` (`user_id`) COMMENT 'user 索引（多用户隔离）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='基金卖出流水表';

-- ================================================
-- 表说明：
-- 1. 存储基金卖出（赎回）记录，目前仅支持手动录入（卖出份额）
-- 2. 同一基金同一天只能卖出一次（通过唯一索引保证）
-- 3. sell_status 字段表示卖出状态：PENDING-待处理，SUCCESS-成功，FAILED-失败
-- 4. 卖出金额 amt 不扣手续费：amt = shares × 卖出当日单位净值
-- 5. realized_profit 已实现盈亏 = (卖出净值 - 持仓成本价) × 卖出份额
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
