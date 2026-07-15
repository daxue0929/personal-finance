SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 为position表添加唯一索引
-- 确保同一基金代码在未删除状态下只有一条持仓记录
-- ================================================

ALTER TABLE `position`
ADD UNIQUE KEY `uk_fund_code_del` (`fund_code`, `del_flag`) COMMENT '基金代码+删除标志唯一索引';

SET FOREIGN_KEY_CHECKS = 1;