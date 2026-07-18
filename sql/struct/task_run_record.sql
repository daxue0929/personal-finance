SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 任务执行记录表
-- 每次任务执行（cron/手动）一条记录，含状态机 RUNNING/SUCCESS/FAILED/SKIPPED。
-- 供前端「执行计划」弹窗查看历史执行情况（状态/耗时/开始结束/trace_id）。
-- trace_id 关联 system_log.trace_id，可串联查看本次执行的完整日志。
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `task_run_record`;

CREATE TABLE `task_run_record` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `task_func` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '任务函数名（关联 task_schedule.task_func）',
  `task_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '任务名（冗余，便于展示）',
  `trigger_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '触发类型：cron-定时触发 / manual-手动触发',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '状态：RUNNING-运行中 / SUCCESS-成功 / FAILED-失败 / SKIPPED-跳过(防重叠)',
  `trace_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '链路ID（关联 system_log.trace_id）',
  `triggered_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '触发者：scheduler(cron) / 用户名(manual)',
  `start_time` datetime DEFAULT NULL COMMENT '开始时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  `duration_ms` int DEFAULT NULL COMMENT '耗时（毫秒）',
  `error_message` text COMMENT '失败时的错误信息',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_task_func_status` (`task_func`,`status`) USING BTREE COMMENT '任务+状态索引（防重叠查询用）',
  KEY `idx_task_func_start` (`task_func`,`start_time`) USING BTREE COMMENT '任务+开始时间索引（历史查询用）',
  KEY `idx_trace_id` (`trace_id`) USING BTREE COMMENT '链路ID索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='任务执行记录表';

-- ================================================
-- 表说明：
-- 1. 每条记录代表一次任务执行，状态机 RUNNING -> SUCCESS/FAILED；防重叠跳过记 SKIPPED
-- 2. IDLE（空闲）为派生态：某 task_func 当前无 status='RUNNING' 的记录即空闲，不单独存
-- 3. 无 del_flag：执行记录是流水，不软删，靠 clean_records_before 按时间清理（清理跳过 RUNNING）
-- 4. trace_id 与 system_log.trace_id 同值，可双向串联查询
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
