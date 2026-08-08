-- ============================================================================
-- 多用户迁移脚本 (PRD multi-user AC-1)
-- 创建日期: 2026-08-08
-- 配套任务: tasks/tasks-multi-user.md Task 2
--
-- 背景：
--   prd-user-login 已上线 User 表 + 登录态 + admin 装饰器，但 6 张业务表
--   （portfolio / fund_buyer / fund_seller / position / position_daily_snapshot /
--   fund_dip_plan）无 user_id 隔离。本脚本加 user_id 字段 + 新增 invite_code 表。
--
-- 6 步迁移（DDL 一次性执行，**不可中断**）：
--   1. ADD COLUMN user_id BIGINT NULL（先 NULL 避免历史数据冲突）
--   2. UPDATE user_id = admin.id（一次性老数据归 admin）
--   3. MODIFY COLUMN user_id BIGINT NOT NULL（强制非空）
--   4. ADD INDEX idx_user_id（性能索引）
--   5. CREATE TABLE invite_code（新表）
--   6. 兜底校验：SELECT WHERE user_id IS NULL 应全部为 0
--
-- 用法：
--   开发环境：mysql -uroot -p < 08_add_user_id_to_business_tables.sql
--   生产部署：先停 web + scheduler 进程 → 跑脚本 → 启动新版本
--
-- 风险：
--   - DDL 不可逆：执行前确保已备份生产库
--   - 步骤 1-4 必须按顺序执行（NULL 迁移 → NOT NULL 是 DDL 规范）
--   - 步骤 6 应为 0 行；如 > 0 则说明某张表忘记 UPDATE，立即停手排查
-- ============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 步骤 1: 6 张业务表 ADD COLUMN user_id BIGINT NULL
-- ============================================================================
ALTER TABLE `portfolio`                ADD COLUMN `user_id` BIGINT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `fund_buyer`               ADD COLUMN `user_id` BIGINT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `fund_seller`              ADD COLUMN `user_id` BIGINT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `position`                 ADD COLUMN `user_id` BIGINT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `position_daily_snapshot`  ADD COLUMN `user_id` BIGINT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `fund_dip_plan`            ADD COLUMN `user_id` BIGINT NULL COMMENT '所属 user（多用户隔离）';

-- ============================================================================
-- 步骤 2: 老数据归属 admin（一次性迁移）
-- ============================================================================
UPDATE `portfolio`                SET user_id = (SELECT id FROM `user` WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL;
UPDATE `fund_buyer`               SET user_id = (SELECT id FROM `user` WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL;
UPDATE `fund_seller`              SET user_id = (SELECT id FROM `user` WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL;
UPDATE `position`                 SET user_id = (SELECT id FROM `user` WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL;
UPDATE `position_daily_snapshot`  SET user_id = (SELECT id FROM `user` WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL;
UPDATE `fund_dip_plan`            SET user_id = (SELECT id FROM `user` WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL;

-- ============================================================================
-- 步骤 3: 强制 user_id NOT NULL
-- ============================================================================
ALTER TABLE `portfolio`                MODIFY COLUMN `user_id` BIGINT NOT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `fund_buyer`               MODIFY COLUMN `user_id` BIGINT NOT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `fund_seller`              MODIFY COLUMN `user_id` BIGINT NOT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `position`                 MODIFY COLUMN `user_id` BIGINT NOT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `position_daily_snapshot`  MODIFY COLUMN `user_id` BIGINT NOT NULL COMMENT '所属 user（多用户隔离）';
ALTER TABLE `fund_dip_plan`            MODIFY COLUMN `user_id` BIGINT NOT NULL COMMENT '所属 user（多用户隔离）';

-- ============================================================================
-- 步骤 4: 加性能索引 idx_user_id
-- ============================================================================
ALTER TABLE `portfolio`                ADD INDEX `idx_user_id` (`user_id`);
ALTER TABLE `fund_buyer`               ADD INDEX `idx_user_id` (`user_id`);
ALTER TABLE `fund_seller`              ADD INDEX `idx_user_id` (`user_id`);
ALTER TABLE `position`                 ADD INDEX `idx_user_id` (`user_id`);
ALTER TABLE `position_daily_snapshot`  ADD INDEX `idx_user_id` (`user_id`);
ALTER TABLE `fund_dip_plan`            ADD INDEX `idx_user_id` (`user_id`);

-- ============================================================================
-- 步骤 5: 新表 invite_code
-- ============================================================================
CREATE TABLE `invite_code` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `code` VARCHAR(8) NOT NULL COMMENT '8 位 a-z A-Z 0-9 邀请码（UNIQUE）',
  `created_by` BIGINT NOT NULL COMMENT '生成该码的 user_id（admin）',
  `expires_at` DATETIME NOT NULL COMMENT '过期时间（生成时刻 +7 天）',
  `used_at` DATETIME NULL COMMENT '使用时间（NULL = 未用）',
  `used_by` BIGINT NULL COMMENT '使用者 user_id',
  `del_flag` CHAR(1) DEFAULT '1' COMMENT '1 正常 / 0 软删（admin 禁用）',
  `create_time` DATETIME DEFAULT NULL,
  `update_time` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`) COMMENT '邀请码唯一索引',
  KEY `idx_expires` (`expires_at`) COMMENT '过期时间索引',
  KEY `idx_created_by` (`created_by`) COMMENT '生成者索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='邀请码表（multi-user 注册流）';

-- ============================================================================
-- 步骤 6: 兜底校验（应为 0 行；> 0 立即停手排查）
-- ============================================================================
SELECT 'portfolio'                AS tbl, COUNT(*) AS null_count FROM `portfolio`                WHERE `user_id` IS NULL
UNION ALL
SELECT 'fund_buyer'               AS tbl, COUNT(*) AS null_count FROM `fund_buyer`               WHERE `user_id` IS NULL
UNION ALL
SELECT 'fund_seller'              AS tbl, COUNT(*) AS null_count FROM `fund_seller`              WHERE `user_id` IS NULL
UNION ALL
SELECT 'position'                 AS tbl, COUNT(*) AS null_count FROM `position`                 WHERE `user_id` IS NULL
UNION ALL
SELECT 'position_daily_snapshot'  AS tbl, COUNT(*) AS null_count FROM `position_daily_snapshot`  WHERE `user_id` IS NULL
UNION ALL
SELECT 'fund_dip_plan'            AS tbl, COUNT(*) AS null_count FROM `fund_dip_plan`            WHERE `user_id` IS NULL;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- 后续步骤（不在本脚本，需分别跑）：
--   7. 改存储过程：sp_insert_fund_buyer_by_change 加 p_user_id 入参（sql/program/买入.sql）
--   8. 改存储过程：backup_position_daily_snapshot SELECT 段加 p.user_id（sql/program/持仓每日快照备份.sql）
--
-- 已完成的 DDL 同步（无需重跑）：
--   sql/struct/ 6 张业务表（portfolio / fund_buyer / fund_seller / position /
--   position_daily_snapshot / fund_dip_plan）均已加 user_id 列 + idx_user_id
--   索引。这些是 fresh install 用的 DDL 源，ALTER 在本脚本步骤 1 已覆盖。
-- ============================================================================
