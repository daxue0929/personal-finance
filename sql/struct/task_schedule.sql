CREATE TABLE IF NOT EXISTS `task_schedule` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `task_name` varchar(100) NOT NULL COMMENT '任务名称',
  `task_func` varchar(200) NOT NULL COMMENT '任务函数名',
  `cron_expression` varchar(100) NOT NULL COMMENT 'Cron表达式',
  `enabled` tinyint(1) DEFAULT '1' COMMENT '是否启用',
  `description` varchar(500) DEFAULT NULL COMMENT '任务描述',
  `del_flag` char(1) DEFAULT '1' COMMENT '删除标记',
  `create_by` varchar(64) DEFAULT NULL COMMENT '创建人',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) DEFAULT NULL COMMENT '更新人',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_func` (`task_func`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='定时任务配置表';
