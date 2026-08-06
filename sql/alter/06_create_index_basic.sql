-- ================================================
-- 新增指数基础表（生产环境增量建表脚本）
-- 配套功能：PRD "index-basic-table" + Design "index-basic-table"
--
-- 与 create_fund_dip_plan_table.sql 一致：使用 CREATE TABLE IF NOT EXISTS
-- struct/index_basic.sql 是 DROP+CREATE 破坏性脚本（仅全新建库用），
-- 本脚本可在已有数据的生产库安全执行。
-- 二次执行幂等：表已存在则跳过；4 条初始数据用 INSERT IGNORE 防重复。
-- ================================================

CREATE TABLE IF NOT EXISTS `index_basic` (
  `index_code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '指数代码（6位数字，主键）',
  `market` varchar(4) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '市场前缀（sh=沪市 / sz=深市）',
  `index_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '指数中文名（如 沪深300）',
  `index_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '宽基指数' COMMENT '指数类型（宽基指数/行业指数/策略指数）',
  `enabled` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用抓取（1启用 0停用）',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '1' COMMENT '删除标志（1正常 0删除，软删）',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '创建者',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间（北京时间）',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '更新者',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间（北京时间）',
  PRIMARY KEY (`index_code`) USING BTREE,
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_enabled_del` (`enabled`,`del_flag`) COMMENT '启用+删除标志复合索引（fetch_all_indexes_task 扫描用）',
  KEY `idx_market` (`market`) COMMENT '市场索引（按市场过滤）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='指数基础信息表（fetch_all_indexes_task 元数据源）';

-- ================================================
-- 表说明：
-- 1. 存储需要抓取的指数元信息（代码/市场/名称/类型/启用），与 index_info（行情数据）解耦
-- 2. fetch_all_indexes_task 启动时读 enabled=1 AND del_flag='1' 全量遍历
-- 3. 8月5日 index_info 丢失中文名 bug 的根因修复点（storage 4 道 name 兜底源）
-- 4. 软删 del_flag='0' 保留历史 index_info 行不级联清理
-- 5. 020292 联动仍硬编码在 task 内（待后续加 linked_fund_code 字段，PRD §5 非目标）
-- ================================================

-- ================================================
-- 初始数据：4 条老指数
-- 与 INDEX_NAME_MAP + 历史 index_info 行对齐，作为 fetch_all_indexes_task 启动后第一次抓取的元数据源
-- INSERT IGNORE 保证二次执行幂等
-- ================================================

INSERT IGNORE INTO `index_basic` (`index_code`, `market`, `index_name`, `index_type`, `enabled`, `del_flag`, `create_by`, `create_time`, `update_by`, `update_time`) VALUES
  ('000300', 'sh', '沪深300',  '宽基指数', 1, '1', 'system_migration', NOW(), 'system_migration', NOW()),
  ('000688', 'sh', '科创50',   '宽基指数', 1, '1', 'system_migration', NOW(), 'system_migration', NOW()),
  ('000698', 'sh', '科创100',  '宽基指数', 1, '1', 'system_migration', NOW(), 'system_migration', NOW()),
  ('399673', 'sz', '创业板50', '宽基指数', 1, '1', 'system_migration', NOW(), 'system_migration', NOW());

-- ==================== 验证 ====================
-- 跑完此脚本后建议确认：
-- SHOW CREATE TABLE index_basic\G
-- SELECT * FROM index_basic ORDER BY index_code;
-- 预期：4 行（000300/000688/000698/399673），全 enabled=1 del_flag='1'
