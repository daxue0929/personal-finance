SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 存储过程：备份当天基金净值到历史表
-- ----------------------------
DELIMITER $$

DROP PROCEDURE IF EXISTS `backup_fund_nav_history`$$

CREATE PROCEDURE `backup_fund_nav_history`()
BEGIN
    DECLARE today_date DATE;
    SET today_date = CURDATE();
    
    -- 删除当天已存在的历史数据（允许重复执行）
    DELETE FROM fund_nav_history 
    WHERE nav_date = today_date;
    
    -- 插入当天的基金净值数据，同时计算日涨跌幅
    INSERT INTO fund_nav_history (
        fund_code,
        fund_name,
        nav_date,
        unit_nav,
        daily_growth_rate,
        source,
        create_time
    )
    SELECT 
        fi.fund_code,
        fi.fund_name,
        fi.net_value_date,
        fi.net_asset_value,
        -- 计算日涨跌幅：(今日净值 - 昨日净值) / 昨日净值 × 100%
        CASE 
            WHEN prev.unit_nav IS NOT NULL THEN 
                ROUND((fi.net_asset_value - prev.unit_nav) / prev.unit_nav * 100, 4)
            ELSE 
                NULL 
        END AS daily_growth_rate,
        'system',
        NOW()
    FROM fund_info fi
    LEFT JOIN fund_nav_history prev 
        ON fi.fund_code = prev.fund_code 
        AND prev.nav_date = DATE_SUB(today_date, INTERVAL 1 DAY)
    WHERE fi.del_flag = '1'
      AND fi.net_value_date IS NOT NULL
      AND fi.net_asset_value IS NOT NULL
      AND fi.net_value_date = today_date;
    
    SELECT ROW_COUNT() AS inserted_rows;
END$$

DELIMITER ;

-- ----------------------------
-- 开启事件调度器
-- ----------------------------
SET GLOBAL event_scheduler = ON;

-- ----------------------------
-- 事件调度器：每天下午3点03分执行备份
-- ----------------------------
DROP EVENT IF EXISTS event_backup_fund_nav;

DELIMITER $$

CREATE EVENT event_backup_fund_nav
ON SCHEDULE EVERY 1 DAY
STARTS CONCAT(CURDATE(), ' 15:03:00')
ON COMPLETION PRESERVE
ENABLE
DO
BEGIN
    CALL backup_fund_nav_history();
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;
