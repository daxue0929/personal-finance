-- ================================================
-- 基金买入流水表添加买入份额字段
-- ================================================

-- 添加 shares 字段
ALTER TABLE `fund_buyer` 
ADD COLUMN `shares` decimal(15,4) DEFAULT NULL COMMENT '买入份额（日舍五入，保留两位小数）' AFTER `buy_status`;

-- 添加复合索引（包含shares字段用于查询）
ALTER TABLE `fund_buyer`
ADD INDEX `idx_status_shares` (`buy_status`, `shares`) COMMENT '状态+份额复合索引';
