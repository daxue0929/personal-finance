-- ================================================
-- task_schedule 新增沪深300、创业板50指数抓取任务配置
-- cron: * 9-15 * * mon-fri（交易时段每分钟，与现有 kc50/kc100 任务一致）
-- 注意：任务函数 fetch_hs300_index_task / fetch_cyb50_index_task
--   需 scheduler 进程重启后由 register_task 注册（热加载仅重读 cron 配置，不重载代码）
-- ================================================

INSERT INTO `task_schedule` (`task_name`, `task_func`, `cron_expression`, `enabled`, `del_flag`, `description`, `create_by`, `create_time`, `update_by`, `update_time`)
VALUES
  ('沪深300指数抓取任务',  'fetch_hs300_index_task', '* 9-15 * * mon-fri', 1, '1', '每分钟执行一次，抓取沪深300指数(000300)实时数据',  'system', NOW(), 'system', NOW()),
  ('创业板50指数抓取任务', 'fetch_cyb50_index_task', '* 9-15 * * mon-fri', 1, '1', '每分钟执行一次，抓取创业板50指数(399673)实时数据', 'system', NOW(), 'system', NOW());
