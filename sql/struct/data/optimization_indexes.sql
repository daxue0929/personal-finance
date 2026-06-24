-- 数据库索引优化脚本
-- MySQL 5.7 兼容版本

DELIMITER $$

-- 创建安全添加索引的存储过程
CREATE PROCEDURE IF NOT EXISTS AddIndexIfNotExists(
    IN tableName VARCHAR(64),
    IN indexName VARCHAR(64),
    IN indexColumns VARCHAR(512)
)
BEGIN
    DECLARE indexCount INT DEFAULT 0;
    
    -- 检查索引是否存在
    SELECT COUNT(*) INTO indexCount
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE table_schema = DATABASE()
      AND table_name = tableName
      AND index_name = indexName;
    
    -- 如果索引不存在，则创建
    IF indexCount = 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', tableName, '` ADD INDEX `', indexName, '` (', indexColumns, ')');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

DELIMITER ;

-- 1. portfolio表索引
CALL AddIndexIfNotExists('portfolio', 'idx_del_flag', 'del_flag');
CALL AddIndexIfNotExists('portfolio', 'idx_name_del', 'name, del_flag');
CALL AddIndexIfNotExists('portfolio', 'idx_create_time', 'create_time');

-- 2. position表索引
CALL AddIndexIfNotExists('position', 'idx_del_flag', 'del_flag');
CALL AddIndexIfNotExists('position', 'idx_fund_code_del', 'fund_code, del_flag');
CALL AddIndexIfNotExists('position', 'idx_fund_name_del', 'fund_name, del_flag');
CALL AddIndexIfNotExists('position', 'idx_buy_date', 'buy_date');
CALL AddIndexIfNotExists('position', 'idx_current_value', 'current_value');
CALL AddIndexIfNotExists('position', 'idx_profit_loss', 'profit_loss');

-- 3. portfolio_position表索引
CALL AddIndexIfNotExists('portfolio_position', 'idx_del_flag', 'del_flag');
CALL AddIndexIfNotExists('portfolio_position', 'idx_portfolio_del', 'portfolio_id, del_flag');
CALL AddIndexIfNotExists('portfolio_position', 'idx_position_del', 'position_id, del_flag');
CALL AddIndexIfNotExists('portfolio_position', 'idx_portfolio_position', 'portfolio_id, position_id');

-- 4. fund_info表索引
CALL AddIndexIfNotExists('fund_info', 'idx_del_flag', 'del_flag');
CALL AddIndexIfNotExists('fund_info', 'idx_fund_code_del', 'fund_code, del_flag');
CALL AddIndexIfNotExists('fund_info', 'idx_fund_name_del', 'fund_name, del_flag');
CALL AddIndexIfNotExists('fund_info', 'idx_net_value_date', 'net_value_date');
CALL AddIndexIfNotExists('fund_info', 'idx_fund_type', 'fund_type');

-- 5. fund_buyer表索引
CALL AddIndexIfNotExists('fund_buyer', 'idx_del_flag', 'del_flag');
CALL AddIndexIfNotExists('fund_buyer', 'idx_fund_code_del', 'fund_code, del_flag');
CALL AddIndexIfNotExists('fund_buyer', 'idx_fund_name_del', 'fund_name, del_flag');
CALL AddIndexIfNotExists('fund_buyer', 'idx_time', 'time');
CALL AddIndexIfNotExists('fund_buyer', 'idx_buy_status', 'buy_status');
CALL AddIndexIfNotExists('fund_buyer', 'idx_time_status', 'time, buy_status');

-- 6. fund_nav_history表索引（无del_flag字段）
CALL AddIndexIfNotExists('fund_nav_history', 'idx_fund_code', 'fund_code');
CALL AddIndexIfNotExists('fund_nav_history', 'idx_nav_date', 'nav_date');
CALL AddIndexIfNotExists('fund_nav_history', 'idx_fund_date', 'fund_code, nav_date');
CALL AddIndexIfNotExists('fund_nav_history', 'idx_create_time', 'create_time');

-- 7. task_schedule表索引
CALL AddIndexIfNotExists('task_schedule', 'idx_del_flag', 'del_flag');
CALL AddIndexIfNotExists('task_schedule', 'idx_task_func_del', 'task_func, del_flag');
CALL AddIndexIfNotExists('task_schedule', 'idx_enabled_del', 'enabled, del_flag');
CALL AddIndexIfNotExists('task_schedule', 'idx_create_time', 'create_time');

-- 创建复合索引以优化特定查询

-- 优化组合持仓查询：portfolio_id, position_id, del_flag 的复合索引
CALL AddIndexIfNotExists('portfolio_position', 'idx_portfolio_position_del', 'portfolio_id, position_id, del_flag');

-- 优化按基金代码查询：fund_code, del_flag, net_value_date 的复合索引
CALL AddIndexIfNotExists('fund_info', 'idx_fund_code_date_del', 'fund_code, net_value_date, del_flag');

-- 优化买入记录查询：fund_code, time, buy_status 的复合索引
CALL AddIndexIfNotExists('fund_buyer', 'idx_fund_time_status_del', 'fund_code, time, buy_status, del_flag');

-- 优化持仓统计查询：buy_date, fund_code 的复合索引
CALL AddIndexIfNotExists('position', 'idx_buy_date_fund', 'buy_date, fund_code');

-- 删除存储过程（可选）
DROP PROCEDURE IF EXISTS AddIndexIfNotExists;
