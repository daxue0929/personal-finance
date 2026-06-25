SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 系统日志表
-- 存储系统运行过程中的日志信息，用于问题排查和审计
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `system_log`;

CREATE TABLE `system_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '日志ID（主键，自增）',
  `level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）',
  `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '日志分类（task/crawler/api/database/system）',
  `message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '日志消息内容',
  `trace_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '请求追踪ID',
  `request_method` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT 'HTTP请求方法（GET/POST/PUT/DELETE）',
  `request_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT 'HTTP请求路径',
  `request_ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '客户端IP地址',
  `task_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '任务名称',
  `error_stack` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci COMMENT '错误堆栈信息',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_level` (`level`) COMMENT '日志级别索引',
  KEY `idx_category` (`category`) COMMENT '日志分类索引',
  KEY `idx_trace_id` (`trace_id`) COMMENT '追踪ID索引',
  KEY `idx_create_time` (`create_time`) COMMENT '创建时间索引',
  KEY `idx_level_time` (`level`,`create_time`) COMMENT '日志级别+创建时间复合索引',
  KEY `idx_category_time` (`category`,`create_time`) COMMENT '日志分类+创建时间复合索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='系统日志表';

SET FOREIGN_KEY_CHECKS = 1;

-- ================================================
-- 表说明：
-- 1. 用于存储系统运行过程中的所有日志信息
-- 2. 支持通过日志级别、分类、时间等维度进行查询
-- 3. trace_id用于关联同一请求的多条日志
-- 4. 使用异步插入方式，避免影响主业务性能
-- ================================================