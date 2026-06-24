SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 持仓组合与持仓关联表
-- 建立组合与持仓之间的多对多关系
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `portfolio_position`;

CREATE TABLE `portfolio_position` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `portfolio_id` bigint NOT NULL COMMENT '组合ID（关联portfolio.id）',
  `position_id` bigint NOT NULL COMMENT '持仓ID（关联position.id）',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标志（1正常 0删除）',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_portfolio_position` (`portfolio_id`,`position_id`) USING BTREE COMMENT '组合ID+持仓ID复合索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_portfolio_del` (`portfolio_id`,`del_flag`) COMMENT '组合ID+删除标志复合索引',
  KEY `idx_position_del` (`position_id`,`del_flag`) COMMENT '持仓ID+删除标志复合索引',
  KEY `idx_portfolio_position_del` (`portfolio_id`,`position_id`,`del_flag`) COMMENT '组合ID+持仓ID+删除标志复合索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC COMMENT='持仓组合与持仓关联表';

-- ================================================
-- 表说明：
-- 1. 一个组合可以包含多个持仓
-- 2. 一个持仓可以属于多个组合
-- 3. 关联关系通过此表维护
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
