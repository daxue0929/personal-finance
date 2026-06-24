SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 定时任务配置表
-- 存储定时任务的配置信息
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `task_schedule`;

CREATE TABLE `task_schedule` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `task_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '任务名称',
  `task_func` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '任务函数名',
  `cron_expression` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Cron表达式',
  `enabled` tinyint(1) DEFAULT '1' COMMENT '是否启用（1启用 0禁用）',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '任务描述',
  `del_flag` char(1) COLLATE utf8mb4_unicode_ci DEFAULT '1' COMMENT '删除标记（1正常 0删除）',
  `create_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '更新人',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_func` (`task_func`) COMMENT '任务函数名唯一索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_task_func_del` (`task_func`,`del_flag`) COMMENT '任务函数名+删除标志复合索引',
  KEY `idx_enabled_del` (`enabled`,`del_flag`) COMMENT '启用状态+删除标志复合索引',
  KEY `idx_create_time` (`create_time`) COMMENT '创建时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='定时任务配置表';

-- ================================================
-- 表说明：
-- 1. 存储定时任务的配置信息
-- 2. task_func为任务函数名，需唯一
-- 3. cron_expression为Cron表达式，用于指定任务执行时间
-- 4. enabled字段控制任务是否启用
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
