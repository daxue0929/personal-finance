SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 持仓每日快照表
-- 存储每个有效持仓每天的快照（份额/成本/现价/市值/盈亏），
-- 供持仓分析页绘制盈亏比例、持仓金额等历史曲线。
-- 盈亏在快照时按当日 fund_info.net_asset_value 重算。
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `position_daily_snapshot`;

CREATE TABLE `position_daily_snapshot` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `position_id` bigint NOT NULL COMMENT '持仓ID（关联 position.id，无物理外键）',
  `snapshot_date` date NOT NULL COMMENT '快照日期',
  `fund_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '基金代码（冗余，便于查询）',
  `fund_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '基金名称（冗余）',
  `shares` decimal(15,4) DEFAULT '0.0000' COMMENT '快照时点份额',
  `cost_price` decimal(7,4) DEFAULT '0.0000' COMMENT '加权成本价',
  `current_price` decimal(7,4) DEFAULT '0.0000' COMMENT '当日净值（重算盈亏用）',
  `cost_amount` decimal(15,2) DEFAULT '0.00' COMMENT '成本金额 = 份额 × 成本价',
  `current_value` decimal(15,2) DEFAULT '0.00' COMMENT '市值 = 份额 × 当日净值',
  `profit_loss` decimal(15,2) DEFAULT '0.00' COMMENT '盈亏 = 市值 - 成本金额',
  `profit_loss_rate` decimal(6,2) DEFAULT '0.00' COMMENT '盈亏比例（%）= 盈亏 / 成本金额 × 100',
  `source` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT 'manual' COMMENT '数据来源（manual手动/system系统备份）',
  `user_id` bigint NOT NULL DEFAULT '1' COMMENT '所属 user（multi-user 隔离，从 position 携带）',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE KEY `idx_position_date` (`position_id`,`snapshot_date`) USING BTREE COMMENT '持仓ID+快照日期唯一索引',
  KEY `idx_position_id` (`position_id`) USING BTREE COMMENT '持仓ID索引',
  KEY `idx_snapshot_date` (`snapshot_date`) USING BTREE COMMENT '快照日期索引',
  KEY `idx_fund_code` (`fund_code`) USING BTREE COMMENT '基金代码索引',
  KEY `idx_user_id` (`user_id`) USING BTREE COMMENT 'user 索引（multi-user 隔离）',
  KEY `idx_create_time` (`create_time`) COMMENT '创建时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='持仓每日快照表';

-- ================================================
-- 表说明：
-- 1. 每条记录代表某持仓某日的快照，唯一键 (position_id, snapshot_date)
-- 2. 盈亏按当日 fund_info.net_asset_value 重算，不照搬 position 表的冻结值
-- 3. source: manual-手动录入，system-定时备份任务生成
-- 4. 持仓软删除后历史快照保留，供历史分析
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
