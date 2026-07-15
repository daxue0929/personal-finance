-- ============================================================================
-- 修复脚本：补加被 date guard 错误跳过的 4 笔历史买入份额到对应持仓
-- ============================================================================
--
-- 背景：
--   calculate_buyer_shares_task._update_position 原先用 position.buy_date 做幂等水位
--   （流水买入日期 <= 持仓买入日期 则跳过），导致补录历史/同日买入被错误跳过，
--   份额虽算成 SUCCESS 但未累加进持仓。共 4 笔（system_log 可查）：
--     持仓14 中证卫星025491 流水112 (7.13) 468.7793 份 500 元
--     持仓16 中证白酒012414 流水111 (7.13)  98.9120 份  50 元
--     持仓10 科创100 020292 流水89  (7.07)  33.1716 份  80 元
--     持仓11 创业板50 160424 流水66  (6.26)  31.1876 份 100 元
--
-- 修复方式：增量补加（不能从买入流水重算，因持仓含手动/历史基线份额）。
--   各字段用 _compute_buyer_accumulation（加权成本法）重算，与代码实现同源：
--     new_total_shares = old_shares + buy_shares
--     new_cost_amount  = round(old_cost_amount + buy_amt, 2)
--     weighted_cost_price = new_cost_amount / new_total_shares
--     current_value   = round(new_total_shares * current_price, 2)
--     profit_loss     = round(current_value - new_cost_amount, 2)
--     profit_loss_rate= round(profit_loss / new_cost_amount * 100, 2)
--
-- 幂等性：每条 UPDATE 带 WHERE 守卫——只有当持仓份额等于「修复前快照值」时才更新。
--   重跑时持仓份额已是修复后值，守卫不匹配，UPDATE 影响 0 行，不会双倍加。
--   执行前先用前置断言 SELECT 确认 4 条持仓仍是修复前状态。
--
-- 用法：先跑下方「前置断言」SELECT，确认 4 行值与注释一致；再跑 4 条 UPDATE；
--       最后跑「后置校验」SELECT 确认修复后值。
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 0. 前置断言：确认 4 个持仓仍是「修复前」状态（shares 与注释一致才可执行）
--    预期：持仓14=2047.6588 / 持仓16=12155.8298 / 持仓10=869.0113 / 持仓11=719.8316
-- ----------------------------------------------------------------------------
SELECT id, fund_code, fund_name, shares, cost_amount, cost_price, current_price
FROM position WHERE id IN (10, 11, 14, 16) ORDER BY id;


-- ----------------------------------------------------------------------------
-- 1. 增量补加 4 笔被跳过的份额（带 WHERE 守卫，幂等可重入）
-- ----------------------------------------------------------------------------

-- 持仓14 中证卫星025491：+468.7793 份 / +500.00 元
--   修复前 shares=2047.6588, cost_amount=2239.99
--   修复后 shares=2516.4381, cost_amount=2739.99, cost_price=1.0888,
--           current_value=2558.71, profit_loss=-181.28, rate=-6.62
UPDATE position
SET shares      = 2516.4381,
    cost_amount = 2739.99,
    cost_price  = 1.0888,
    current_value      = 2558.71,
    profit_loss        = -181.28,
    profit_loss_rate   = -6.62,
    update_by   = 'system',
    update_time = NOW()
WHERE id = 14
  AND fund_code = '025491'
  AND shares = 2047.6588;   -- 守卫：仅修复前状态命中

-- 持仓16 中证白酒012414：+98.9120 份 / +50.00 元
--   修复前 shares=12155.8298, cost_amount=6350.06
--   修复后 shares=12254.7418, cost_amount=6400.06, cost_price=0.5223,
--           current_value=6233.99, profit_loss=-166.07, rate=-2.59
UPDATE position
SET shares      = 12254.7418,
    cost_amount = 6400.06,
    cost_price  = 0.5223,
    current_value      = 6233.99,
    profit_loss        = -166.07,
    profit_loss_rate   = -2.59,
    update_by   = 'system',
    update_time = NOW()
WHERE id = 16
  AND fund_code = '012414'
  AND shares = 12155.8298;  -- 守卫：仅修复前状态命中

-- 持仓10 科创100 020292：+33.1716 份 / +80.00 元
--   修复前 shares=869.0113, cost_amount=1964.25
--   修复后 shares=902.1829, cost_amount=2044.25, cost_price=2.2659,
--           current_value=2029.82, profit_loss=-14.43, rate=-0.71
UPDATE position
SET shares      = 902.1829,
    cost_amount = 2044.25,
    cost_price  = 2.2659,
    current_value      = 2029.82,
    profit_loss        = -14.43,
    profit_loss_rate   = -0.71,
    update_by   = 'system',
    update_time = NOW()
WHERE id = 10
  AND fund_code = '020292'
  AND shares = 869.0113;   -- 守卫：仅修复前状态命中

-- 持仓11 创业板50 160424：+31.1876 份 / +100.00 元
--   修复前 shares=719.8316, cost_amount=2220.00
--   修复后 shares=751.0192, cost_amount=2320.00, cost_price=3.0891,
--           current_value=2182.16, profit_loss=-137.84, rate=-5.94
UPDATE position
SET shares      = 751.0192,
    cost_amount = 2320.00,
    cost_price  = 3.0891,
    current_value      = 2182.16,
    profit_loss        = -137.84,
    profit_loss_rate   = -5.94,
    update_by   = 'system',
    update_time = NOW()
WHERE id = 11
  AND fund_code = '160424'
  AND shares = 719.8316;   -- 守卫：仅修复前状态命中


-- ----------------------------------------------------------------------------
-- 2. 后置校验：确认 4 个持仓已是「修复后」状态
--    预期：持仓14=2516.4381 / 持仓16=12254.7418 / 持仓10=902.1829 / 持仓11=751.0192
-- ----------------------------------------------------------------------------
SELECT id, fund_code, fund_name, shares, cost_amount, cost_price, current_price,
       current_value, profit_loss, profit_loss_rate
FROM position WHERE id IN (10, 11, 14, 16) ORDER BY id;


-- ----------------------------------------------------------------------------
-- 备注：
--   1) 本脚本只补 position 表的份额/成本/盈亏冗余字段，不回溯 position_daily_snapshot
--      历史快照（快照按日备份，历史快照保持原样不影响后续分析，最新日快照会在
--      次3点 backup_position_snapshot_task 自动覆盖）。
--   2) 4 条被跳过的买入流水(buy_id 66/89/111/112)本就是 SUCCESS 状态，无需改状态。
--   3) 代码侧已删除 date guard 并改为原子事务（见 calculate_buyer_shares_task 改造），
--      今后补录历史买入会正常累加持仓，不再出现此类漏加。
-- ----------------------------------------------------------------------------
