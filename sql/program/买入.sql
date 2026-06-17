-- ====================================================================================
-- 基金买入存储过程（MySQL）
-- 说明：此存储过程用于根据基金涨跌幅自动计算并执行买入操作
-- 执行环境：MySQL 5.7+ / MySQL 8.0+
-- 功能：根据输入的基金代码和涨跌幅，自动计算买入金额并插入到 fund_buyer 表
-- ====================================================================================
DELIMITER $$

-- 如果存储过程已存在，则先删除
DROP PROCEDURE IF EXISTS `sp_insert_fund_buyer_by_change`$$

CREATE PROCEDURE `sp_insert_fund_buyer_by_change`(
    IN p_fund_code VARCHAR(10),      -- 基金代码
    IN p_change_percent DECIMAL(6,2)  -- 涨跌幅，单位%，例如 1.5 表示 +1.5%，-2.3 表示 -2.3%
)
BEGIN
    DECLARE v_fund_name VARCHAR(64);
    DECLARE v_fund_code VARCHAR(10);      -- 真实的基金代码（从 fund_info 获取）
    DECLARE v_coefficient DECIMAL(5,4);   -- 买入系数（比如 1.0 代表 100%）
    DECLARE v_amt DECIMAL(7,4);           -- 最终买入金额
    DECLARE v_change DECIMAL(6,2);        -- 涨跌幅数值（带小数）
    DECLARE v_exists INT;                 -- 当天是否已有买入记录（0:无, 1:有）

    -- 设置会话时间区为上海时间
    SET SESSION time_zone = 'Asia/Shanghai'; 


    -- 1. 根据基金代码或基金ID查找基金信息，若不存在则报错
    SELECT fund_code, fund_name INTO v_fund_code, v_fund_name
    FROM fund_info
    WHERE (fund_code = p_fund_code OR fund_id = p_fund_code) AND del_flag = '1';

    IF v_fund_name IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '基金代码不存在或已删除';
    END IF;

    -- 2. 检查当天是否已有该基金的买入记录（使用真实的 fund_code）
    SELECT COUNT(*) INTO v_exists
    FROM fund_buyer
    WHERE fund_code = v_fund_code AND time = CURDATE() AND del_flag = '1';

    -- 3. 时间检查：下午三点之后不允许更新已有数据，但允许插入新数据（补录）
    IF CURTIME() > '15:00:00' AND v_exists = 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '当前时间已过下午三点，不允许修改当天已有数据';
    END IF;

    -- 4. 直接使用输入的涨跌幅（已经是DECIMAL类型）
    SET v_change = p_change_percent;

    -- 5. 根据涨跌幅区间确定买入系数（单位：倍）
    CASE
        -- 下跌区间（负数方向）
        WHEN v_change <= -25 THEN
            SET v_coefficient = 3.00;   -- 300% 买入
        WHEN v_change > -25 AND v_change <= -22.5 THEN
            SET v_coefficient = 2.80;   -- 280%
        WHEN v_change > -22.5 AND v_change <= -20 THEN
            SET v_coefficient = 2.60;
        WHEN v_change > -20 AND v_change <= -17.5 THEN
            SET v_coefficient = 2.40;
        WHEN v_change > -17.5 AND v_change <= -15 THEN
            SET v_coefficient = 2.20;
        WHEN v_change > -15 AND v_change <= -12.5 THEN
            SET v_coefficient = 2.00;
        WHEN v_change > -12.5 AND v_change <= -10 THEN
            SET v_coefficient = 1.80;
        WHEN v_change > -10 AND v_change <= -7.5 THEN
            SET v_coefficient = 1.60;
        WHEN v_change > -7.5 AND v_change <= -5 THEN
            SET v_coefficient = 1.40;
        WHEN v_change > -5 AND v_change < -2.5 THEN
            SET v_coefficient = 1.20;
        
        -- 横盘区间
        WHEN v_change >= -2.5 AND v_change <= 2.5 THEN
            SET v_coefficient = 1.00;
        
        -- 上涨区间（正数方向）
        WHEN v_change > 2.5 AND v_change <= 5 THEN
            SET v_coefficient = 0.90;
        WHEN v_change > 5 AND v_change <= 7.5 THEN
            SET v_coefficient = 0.80;
        WHEN v_change > 7.5 AND v_change <= 10 THEN
            SET v_coefficient = 0.70;
        WHEN v_change > 10 AND v_change <= 12.5 THEN
            SET v_coefficient = 0.60;
        WHEN v_change > 12.5 AND v_change <= 15 THEN
            SET v_coefficient = 0.50;
        WHEN v_change > 15 AND v_change <= 17.5 THEN
            SET v_coefficient = 0.40;
        WHEN v_change > 17.5 AND v_change <= 20 THEN
            SET v_coefficient = 0.30;
        ELSE
            -- 涨幅超过 20%：暂停买入，可以报错或直接返回（这里选择报错）
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '涨幅超过20%，暂停买入';
    END CASE;

    -- 6. 计算买入金额（基础金额固定 100 元）
    SET v_amt = 100 * v_coefficient;

    -- 7. 插入或更新 fund_buyer 表（当天重复执行时更新记录）
    INSERT INTO `fund_buyer` (
        `fund_code`,
        `fund_name`,
        `time`,
        `amt`,
        `type`,
        `policy`,
        `del_flag`,
        `create_by`,
        `create_time`,
        `update_by`,
        `update_time`,
        `remark`,
        `buy_status`
    ) VALUES (
        v_fund_code,                   -- 使用从 fund_info 获取的真实基金代码
        v_fund_name,
        CURDATE(),                     -- 买入日期为当前日期
        v_amt,
        '1',                           -- 1: 手工买入
        '涨跌幅系数策略',               -- 策略说明，可按需调整
        '1',                           -- 正常状态
        'daxue',                       -- 创建者
        DATE_ADD(NOW(), INTERVAL 8 HOUR),  -- 创建时间
        'daxue',                       -- 更新者
        DATE_ADD(NOW(), INTERVAL 8 HOUR),  -- 更新时间
        CONCAT('涨跌幅=', v_change, '%, 系数=', v_coefficient),
        'PENDING'
    ) ON DUPLICATE KEY UPDATE
        `amt` = VALUES(`amt`),
        `update_by` = VALUES(`update_by`),
        `update_time` = VALUES(`update_time`),
        `remark` = VALUES(`remark`),
        `buy_status` = VALUES(`buy_status`);

    -- 8. 输出买入结果
    SELECT
        CURDATE() AS '买入日期',
        v_amt AS '买入金额';

END$$

DELIMITER ;