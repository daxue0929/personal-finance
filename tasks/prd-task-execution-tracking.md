# PRD: 任务执行记录与状态追踪(task-execution-tracking)

**Feature slug**: `task-execution-tracking`

## 1. 背景与功能目标

### 背景
当前任务执行是**同步阻塞**模型:前端点"执行" -> `POST /api/task/run` -> web 转发 scheduler -> `run_job_now` 同步跑完(长任务如 fundf10 抓取 23 只基金约 65 秒)才返回。存在三个问题:

1. **前端超时**:前端 axios 全局 10s(该接口曾加 120s 长超时),长任务仍可能超时弹错(后端实际成功)。
2. **无执行记录**:任务何时跑、跑多久、成功与否,全无记录,只能去 system_log 按 trace_id 模糊推断。
3. **无防重叠**:手动触发路径完全无重叠保护;cron 路径仅靠 APScheduler 内存级 max_instances(不跨重启/手动)。

### 功能目标
新建**任务执行记录表** `task_run_record`,每次任务执行(cron/手动)都有记录并带状态;任务**异步触发**(立即返回"已触发",前端轮询状态);状态机 RUNNING/SUCCESS/FAILED/SKIPPED;**cron 触发前查 DB 防重叠**(RUNNING 则跳过记 SKIPPED);TaskManage 页加"执行计划""执行中"两列,点"执行计划"弹窗看执行记录(含状态/耗时/开始结束/触发类型);提供历史记录清理接口。**通用设计**,未来更多长耗时任务复用。

## 2. 用户故事

- **作为用户**,我希望点"执行"后立即返回"已触发",不用干等,这样长任务不卡前端。
- **作为用户**,我希望看到任务当前是否"运行中",这样知道任务在跑。
- **作为用户**,我希望点"执行计划"看到该任务的历史执行记录(状态/耗时/时间),这样能排查任务执行情况。
- **作为运维**,我希望 cron 触发前检查状态,正在跑则跳过,防止长任务重叠执行。
- **作为运维**,我希望执行记录与 system_log 用 trace_id 串联,这样能一键跳转看本次执行的完整日志。
- **作为运维**,我能清理过老的执行记录,控制表增长。

## 3. 验收标准

### 数据库与 Storage
- [ ] AC1: 新建 `task_run_record` 表(struct + alter 双脚本),字段:id/task_func/task_name/trigger_type(cron|manual)/status(RUNNING|SUCCESS|FAILED|SKIPPED)/trace_id/triggered_by/start_time/end_time/duration_ms/error_message/create_time/update_time;索引 idx_task_func_status(防重叠查询)/idx_task_func_start(历史查询)/idx_trace_id。
- [ ] AC2: 新建 `TaskRunRecordStorage`(继承 StorageBase,自动日志装饰),方法:create_running_record / update_record_status / get_running_record_by_func(防重叠)/ get_record_by_id / get_records_with_pagination / clean_records_before。在 `app/storage/__init__.py` 导出。

### 状态机与执行包装
- [ ] AC3: 新增 `execute_task_with_record` 包装器:重叠检查(查 RUNNING)-> INSERT RUNNING(生成 trace_id)-> 跑任务 -> UPDATE SUCCESS/FAILED(记录 end_time/duration_ms/error_message)。cron 与手动两条路径都覆盖。
- [ ] AC4: cron 触发时(`_add_job` 的 wrapped_func)调 `execute_task_with_record(trigger_type='cron')`,RUNNING 则 INSERT SKIPPED 并 return,不执行任务。
- [ ] AC5: 手动触发时若该任务已 RUNNING,**不触发、不记表**,返回 rejected 标志,前端弹框提示"任务正在运行，请等待完成"。

### 异步触发
- [ ] AC6: `run_job_now` 改异步:INSERT RUNNING + 起后台线程跑任务,立即返回 (record_id, trace_id);`/internal/task/run` 与 `/api/task/run` 立即返回 `{status:'TRIGGERED', record_id, trace_id}`,不再同步等。
- [ ] AC7: `scheduler_proxy.run_task` 超时从 TASK_TIMEOUT(300s)降为 CTRL_TIMEOUT(30s)。

### API
- [ ] AC8: 新增 `GET /api/task-records`(分页+task_func/status 过滤,web 直读 Storage)与 `GET /api/task-records/<id>`(单条状态轮询)。
- [ ] AC9: 新增 `DELETE /api/task-records`(清理 N 天前记录,参照 system_log 清理)。
- [ ] AC10: 任务列表接口 `/api/tasks` 扩展返回每个任务当前 running 状态(是否有 RUNNING 记录),供前端"执行中"列展示。

### 前端
- [ ] AC11: TaskManage 表格加"执行计划"列(按钮,点开弹窗)与"执行中"列(el-tag,运行中/空闲)。
- [ ] AC12: "执行"按钮改异步:触发后立即提示"已触发",不再 await 阻塞;runTask API 去掉 120s 长超时回落全局。
- [ ] AC13: 页面 setInterval 每 5s 轮询任务列表(含 running 状态),onUnmounted 清除(全项目首例轮询,参照 useEChart 清理范式)。
- [ ] AC14: 执行记录弹窗:el-dialog 内嵌 el-table + el-pagination,展示状态(tag)/触发类型/耗时/开始/结束/trace_id(可复制);按 task_func 查询。
- [ ] AC15: 弹窗内"清理历史记录"按钮(保留 N 天),调 DELETE 接口。

### 质量
- [ ] AC16: TDD,`tests/test_task_execution_tracking.py` 先行,测状态机/防重叠/异步触发/记录 CRUD;pytest 全量回归通过。
- [ ] AC17: 前端构建门禁:改 `frontend/src/` 后 `npm run build` 并提交 `dist/`。

## 4. 非目标

- **不改 cron 路径为异步**:cron 路径 APScheduler 已在线程池跑,保持同步(加重叠检查即可),不引入额外线程管理。
- **不新建执行记录独立页面**:用 TaskManage 页内弹窗。
- **不做实时进度推送**(SSE/WebSocket):用轮询。
- **不自动定期清理**:提供手动清理接口,不自动清理(避免新增定时任务)。
- **不改其他任务的执行逻辑**:只加包装器(重叠检查+记录),任务函数本身不动。
- **不动 system_log 表**:仅复用 trace_id 串联,不改日志表结构。

## 5. 依赖

- **现有**:APScheduler(线程池跑 cron)、`run_with_trace_context`(trace_id 生成)、StorageBase(自动日志装饰)、db 连接池、`/api/logs` 已支持 trace_id 过滤(可跳转)。
- **新增**:无新依赖(用标准库 threading)。
- **数据库**:新建 task_run_record 表(struct + alter)。

## 6. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 后台线程异常未更新状态,记录卡 RUNNING | 任务永远被认为在跑,cron 永远跳过 | execute_task_with_record 用 try/finally 保证 UPDATE;异常也记 FAILED |
| 进程重启时正在跑的任务,记录卡 RUNNING | 同上 | 提供手动清理/重置接口;或启动时把 RUNNING 且 start_time 超过阈值的置 FAILED(后续优化) |
| 轮询增加 DB 负载 | 每 5s 查任务列表 | 任务数量少(8 个),查询轻量;可接受 |
| 手动触发与 cron 并发 | 状态竞争 | 都走 execute_task_with_record 的 DB 检查,DB 级防重叠 |
| 异步线程内异常难排查 | 日志可能丢 trace_id | 线程内复用 trace_id ContextVar,日志可串联 |
| 清理接口误删 | 数据丢失 | 清理按天数+确认弹窗,仅删 SKIPPED/SUCCESS/FAILED 不删 RUNNING |

## 7. Open Questions

(Phase 3 澄清后,已无遗留。以下为已澄清决策记录)

- **Q: 执行记录用弹窗还是独立页?** A: 页内弹窗。
- **Q: cron 防重叠范围?** A: 所有任务都防重叠,RUNNING 记 SKIPPED。
- **Q: 状态轮询机制?** A: 定时轮询任务列表(每 5s)。
- **Q: 历史数据增长?** A: 提供清理接口(前端按钮)。
- **Q: 手动触发遇 RUNNING?** A: 不触发、不记表(不记 SKIPPED),返回 rejected 标志,前端弹框提示"任务正在运行，请等待完成"。
