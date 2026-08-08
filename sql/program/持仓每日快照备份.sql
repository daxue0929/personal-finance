SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 存储过程：备份持仓每日快照
-- 说明：备份昨天所有有效持仓（del_flag='1'）的快照，
--       盈亏按当日 fund_info.net_asset_value 重算（position 表盈亏不随净值刷新）。
--       幂等：先按 snapshot_date 删除再插入，允许重复执行。
--       与应用层 backup_position_snapshot_task 公式保持一致：
--         current_value = shares × net_asset_value
--         profit_loss   = current_value - cost_amount
--         profit_loss_rate = profit_loss / cost_amount × 100
-- ================================================
DELIMITER $$

DROP PROCEDURE IF EXISTS `backup_position_daily_snapshot`$$

CREATE PROCEDURE `backup_position_daily_snapshot`()
BEGIN
    -- DECLARE 必须放在 BEGIN 后的最前面（在 SET 之前），否则 MySQL 报语法错误
    DECLARE yesterday_date DATE;

    -- 设置会话时间区为上海时间
    SET SESSION time_zone = 'Asia/Shanghai';

    SET yesterday_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY);

    -- 删除昨天已存在的快照（允许重复执行）
    DELETE FROM position_daily_snapshot
    WHERE snapshot_date = yesterday_date;

    -- 插入昨天所有有效持仓的快照，盈亏按 fund_info 当日净值重算
    INSERT INTO position_daily_snapshot (
        position_id,
        snapshot_date,
        fund_code,
        fund_name,
        shares,
        cost_price,
        current_price,
        cost_amount,
        current_value,
        profit_loss,
        profit_loss_rate,
        source,
        user_id,
        create_time
    )
    SELECT
        p.id                                            AS position_id,
        yesterday_date                                  AS snapshot_date,
        p.fund_code,
        p.fund_name,
        p.shares,
        p.cost_price,
        IFNULL(fi.net_asset_value, p.current_price)     AS current_price,
        p.cost_amount,
        ROUND(p.shares * IFNULL(fi.net_asset_value, p.current_price), 2) AS current_value,
        ROUND(p.shares * IFNULL(fi.net_asset_value, p.current_price) - p.cost_amount, 2) AS profit_loss,
        CASE
            WHEN p.cost_amount > 0 THEN
                ROUND((p.shares * IFNULL(fi.net_asset_value, p.current_price) - p.cost_amount)
                      / p.cost_amount * 100, 2)
            ELSE 0
        END                                             AS profit_loss_rate,
        'system',
        p.user_id                                       AS user_id,  -- multi-user 隔离（从 position 携带）
        NOW()
    FROM position p
    LEFT JOIN fund_info fi ON fi.fund_code = p.fund_code AND fi.del_flag = '1'
    WHERE p.del_flag = '1'
      AND p.shares > 0;

    SELECT ROW_COUNT() AS inserted_rows;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;
