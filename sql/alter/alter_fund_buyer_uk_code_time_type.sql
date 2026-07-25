-- ================================================
-- fund_buyer 唯一键放宽：uk_fund_code_time (fund_code,time) -> (fund_code,time,type)
-- 允许同日同基金不同买入类型各一条（手工+定投），保留按类型幂等
-- 原 (fund_code,time) 太严，与 calculate_buyer_shares_task 的同日合并逻辑矛盾，
-- 且阻挡买入补录（同日已有手工、补录定投会撞键）
-- ================================================

ALTER TABLE `fund_buyer`
  DROP INDEX `uk_fund_code_time`,
  ADD UNIQUE KEY `uk_fund_code_time_type` (`fund_code`,`time`,`type`) USING BTREE COMMENT '基金代码+买入日期+买入类型唯一索引（同日同基金允许不同类型各一条）';
