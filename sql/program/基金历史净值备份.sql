SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 存储过程：备份基金净值到历史表（修正版）
-- 说明：备份昨天的基金净值，计算涨跌幅时自动处理周末情况
-- ----------------------------
DELIMITER $$

DROP PROCEDURE IF EXISTS `backup_fund_nav_history`$$

CREATE PROCEDURE `backup_fund_nav_history`()
BEGIN
    -- 设置会话时区
    SET SESSION time_zone = 'Asia/Shanghai';
    
    DECLARE today_date DATE;
    DECLARE yesterday_date DATE;
    
    SET today_date = CURDATE();
    SET yesterday_date = DATE_SUB(today_date, INTERVAL 1 DAY);
    
    -- 删除昨天已存在的历史数据（允许重复执行）
    DELETE FROM fund_nav_history 
    WHERE nav_date = yesterday_date;
    
    -- 插入昨天的基金净值数据，同时计算涨跌幅
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
        yesterday_date,
        fi.net_asset_value,
        CASE 
            WHEN prev.unit_nav IS NOT NULL THEN 
                ROUND((fi.net_asset_value - prev.unit_nav) / prev.unit_nav * 100, 4)
            ELSE 
                NULL 
        END AS daily_growth_rate,
        'system',
        NOW()
    FROM fund_info fi
    LEFT JOIN (
        SELECT fund_code, unit_nav
        FROM fund_nav_history
        WHERE nav_date = (
            SELECT MAX(nav_date)
            FROM fund_nav_history fn
            WHERE fn.fund_code = fund_nav_history.fund_code
              AND fn.nav_date < yesterday_date
        )
    ) prev ON fi.fund_code = prev.fund_code
    WHERE fi.del_flag = '1'
      AND fi.net_value_date IS NOT NULL
      AND fi.net_asset_value IS NOT NULL
      AND fi.net_value_date >= yesterday_date;
    
    SELECT ROW_COUNT() AS inserted_rows;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;
