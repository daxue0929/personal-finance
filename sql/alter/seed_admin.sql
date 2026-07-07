-- ================================================
-- 初始化默认管理员
-- 用户名: admin  初始密码: admin@123
-- ⚠️ 部署后请立即登录并在「用户管理」页修改密码！
-- ================================================

INSERT INTO `user` (
  `username`, `password_hash`, `display_name`, `role`,
  `enabled`, `session_ttl_minutes`, `del_flag`,
  `create_by`, `create_time`, `update_by`, `update_time`, `remark`
) VALUES (
  'admin',
  'scrypt:32768:8:1$N70xBkJPwhRQyqu3$4a78c36366cef49dfd4d26ddaa18b541f205c611adb0ce36536beb8c0b852951b67424e2542473102ab337ee0a57cacd75212c02e885b1de92884c969e4d1059',
  '管理员',
  'admin',
  1,
  60,
  '1',
  'system',
  NOW(),
  'system',
  NOW(),
  '默认管理员（请尽快修改密码）'
);
