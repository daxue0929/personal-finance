SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ================================================
-- 用户表
-- 系统登录用户（多用户支持第一步）。数据共享：所有用户看到同一套基金/持仓数据。
-- role: admin（管理员，可管理用户）/ user（普通用户）
-- session_ttl_minutes: 该用户登录态保持时长（分钟），登录时据此设置 Cookie 过期
-- ================================================

-- 如果表已存在则删除
DROP TABLE IF EXISTS `user`;

CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID（自增）',
  `username` varchar(64) COLLATE utf8mb4_general_ci NOT NULL COMMENT '用户名（登录标识，唯一）',
  `password_hash` varchar(255) COLLATE utf8mb4_general_ci NOT NULL COMMENT '密码哈希（werkzeug generate_password_hash，scrypt）',
  `display_name` varchar(64) COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '显示名称',
  `role` varchar(20) COLLATE utf8mb4_general_ci DEFAULT 'user' COMMENT '角色（admin 管理员 / user 普通用户）',
  `enabled` tinyint(1) DEFAULT '1' COMMENT '是否启用（1启用 0禁用），禁用用户无法登录且已登录会话立即失效',
  `session_ttl_minutes` int DEFAULT '60' COMMENT '登录态保持时长（分钟），登录时据此设置 Cookie 过期时间',
  `del_flag` char(1) COLLATE utf8mb4_general_ci DEFAULT '1' COMMENT '删除标记（1正常 0删除）',
  `create_by` varchar(64) COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '创建人',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(64) COLLATE utf8mb4_general_ci DEFAULT '' COMMENT '更新人',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `remark` varchar(500) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`) COMMENT '用户名唯一索引',
  KEY `idx_del_flag` (`del_flag`) COMMENT '删除标志索引',
  KEY `idx_username_del` (`username`,`del_flag`) COMMENT '用户名+删除标志复合索引',
  KEY `idx_enabled_del` (`enabled`,`del_flag`) COMMENT '启用状态+删除标志复合索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='系统用户表';

-- ================================================
-- 表说明：
-- 1. 用户登录凭证表，username 唯一
-- 2. password_hash 使用 werkzeug.security.generate_password_hash 生成（scrypt），不可逆
-- 3. role 区分管理员与普通用户；仅管理员可访问用户管理
-- 4. enabled=0 的用户无法登录，且其已建立会话在下次请求时立即失效
-- 5. session_ttl_minutes 控制该用户登录态保持时长（分钟）
-- 6. 软删除（del_flag='0'）遵循全库约定
-- ================================================

SET FOREIGN_KEY_CHECKS = 1;
