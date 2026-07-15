-- ================================================
-- 扩容 fund_buyer.amt 字段：decimal(7,4) -> decimal(10,2)
-- ================================================
-- 背景：fund_buyer.amt 原 decimal(7,4) 整数位仅 3 位（最大 999.9999），
-- 基金买入/定投金额常见 1000 元档位会溢出（严格模式报 1264 out of range，
-- 非严格模式截断为 999.9999 篡改金额）。
-- 与 fund_seller.amt decimal(15,4) 对齐思路，改为 decimal(10,2)：
-- 整数位 8 位（最大 99,999,999.99），小数 2 位（金额语义，无需 4 位小数）。
-- 与 fund_dip_plan.dip_amount decimal(10,2) 完全对齐。
-- ================================================

ALTER TABLE `fund_buyer`
  MODIFY COLUMN `amt` decimal(10,2) DEFAULT '0.0000' COMMENT '买入金额（元）';
