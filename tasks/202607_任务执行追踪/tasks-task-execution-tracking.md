# Task List: 任务执行记录与状态追踪(task-execution-tracking)

**Based on PRD**: `tasks/prd-task-execution-tracking.md`
**Based on Design**: `tasks/design-task-execution-tracking.md`

## Relevant Files

### Files to Create
- `sql/struct/task_run_record.sql` - task_run_record 表结构(DROP+CREATE,全新建库用)
- `sql/alter/create_task_run_record_table.sql` - 生产增量(CREATE TABLE IF NOT EXISTS)
- `data-crawler/app/storage/task_run_record_storage.py` - TaskRunRecord 模型 + TaskRunRecordStorage
- `data-crawler/tests/test_task_execution_tracking.py` - TDD 测试(状态机/防重叠/异步/CRUD)

### Files to Modify
- `data-crawler/app/storage/__init__.py` - 导出 TaskRunRecord/TaskRunRecordStorage
- `data-crawler/app/scheduler/cron_scheduler.py` - execute_task_with_record 包装器 + run_job_now 异步 + _add_job 用包装器 + run_with_trace_context 支持外部 trace_id
- `data-crawler/app/scheduler/control_server.py` - /internal/task/run 立即返回 triggered+record_id+trace_id
- `data-crawler/app/web/scheduler_proxy.py` - run_task 超时降为 CTRL_TIMEOUT
- `data-crawler/app/web/api_server.py` - /api/task/run 返回 triggered + 新增 /api/task-records + /api/tasks 扩展 running
- `frontend/src/api/index.js` - taskApi 新增 getRunHistory/getRunStatus/cleanRunHistory;runTask 去掉 120s 超时
- `frontend/src/views/TaskManage.vue` - 加两列 + 异步执行 + 5s 轮询 + 执行记录弹窗 + 清理按钮

## Implementation Tasks

### 1. task_run_record 表 + Storage
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 1.1 [TDD] 先写 `tests/test_task_execution_tracking.py` 中 Storage 测试:create_running_record / update_record_status / get_running_record_by_func(防重叠查询) / get_record_by_id / get_records_with_pagination / clean_records_before 的 CRUD 与边界(mock DB 或用真实库 fixture)
- [x] 1.2 [TDD] 测状态流转:INSERT RUNNING -> UPDATE SUCCESS/FAILED 后状态/耗时/end_time 正确;clean_records_before 只删非 RUNNING 且 N 天前
- [x] 1.3 实现 `sql/struct/task_run_record.sql`(参照 position_daily_snapshot.sql 风格):字段 id/task_func/task_name/trigger_type/status/trace_id/triggered_by/start_time/end_time/duration_ms/error_message/create_time/update_time;索引 idx_task_func_status/idx_task_func_start/idx_trace_id;无 del_flag
- [x] 1.4 实现 `sql/alter/create_task_run_record_table.sql`(CREATE TABLE IF NOT EXISTS,参照 create_fund_dip_plan_table.sql)
- [x] 1.5 实现 `app/storage/task_run_record_storage.py`:TaskRunRecord(Base) 模型 + TaskRunRecordStorage(StorageBase),照 task_schedule_storage.py 模式(get_db_engine/get_db_session/try-except-finally)
- [x] 1.6 `app/storage/__init__.py` 导出 TaskRunRecord/TaskRunRecordStorage,加入 __all__
- [x] 1.7 跑 `python3 -m pytest tests/test_task_execution_tracking.py -q` 通过(9 passed)+ 生产库建表验证

### 2. 状态机与执行包装器(execute_task_with_record)
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 2.1 [TDD] 测 execute_task_with_record(cron 路径):无 RUNNING 时 INSERT RUNNING -> 跑任务 -> UPDATE SUCCESS(耗时>0);任务抛异常时 UPDATE FAILED(error_message 有值)
- [x] 2.2 [TDD] 测防重叠:已有 RUNNING 时,不执行任务、INSERT SKIPPED(start_time==end_time,duration_ms=0)、return
- [x] 2.3 [TDD] 测 trace_id 复用:记录的 trace_id 与 run_with_trace_context 注入 ContextVar 的一致(日志可串联)
- [x] 2.4 改 `run_with_trace_context`(cron_scheduler.py)支持传入外部 trace_id(复用记录的 trace_id),保留无 trace_id 时自动生成的兼容;顺带补 task_name_var.set(task_name)(Phase 2 发现的缺口)
- [x] 2.5 实现 `execute_task_with_record(task_func, task_name, trigger_type, triggered_by)`:防重叠检查 -> INSERT RUNNING -> 跑任务 -> finally UPDATE SUCCESS/FAILED,参照 design 4.1
- [x] 2.6 `_add_job` 的 wrapped_func(cron_scheduler.py:101-105)改为调 execute_task_with_record(trigger_type='cron')
- [x] 2.7 跑 `python3 -m pytest tests/test_task_execution_tracking.py -q` 通过

### 3. 手动触发异步改造(run_job_now + 链路)
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 3.1 [TDD] 测 run_job_now 异步:返回 {record_id, trace_id} 立即返回(不阻塞);后台线程跑完后记录变 SUCCESS;遇 RUNNING 返回 {rejected:True, message:...} 且不记表、不起线程
- [x] 3.2 [TDD] 测后台线程异常:任务抛异常时记录 UPDATE FAILED,不卡 RUNNING
- [x] 3.3 实现 run_job_now 异步(cron_scheduler.py:147):防重叠(遇 RUNNING 返回 rejected 不记表)-> INSERT RUNNING -> threading.Thread 跑 _run_task_in_thread -> 立即返回 record_id+trace_id。参照 design 4.2
- [x] 3.4 实现 _run_task_in_thread:线程内 run_with_trace_context(复用 trace_id) + finally UPDATE SUCCESS/FAILED
- [x] 3.5 改 control_server.py /internal/task/run(49-73):立即返回 {success, status:'TRIGGERED', record_id, trace_id} 或 {rejected, message},不再同步等
- [x] 3.6 改 scheduler_proxy.py run_task(68-74):超时从 TASK_TIMEOUT(300)降为 CTRL_TIMEOUT(30)
- [x] 3.7 改 api_server.py /api/task/run/<task_func>(332-351):返回 triggered+record_id+trace_id 或 rejected 标志
- [x] 3.8 跑 `python3 -m pytest tests/test_task_execution_tracking.py -q` 通过

### 4. 执行记录 API(web 直读 Storage)
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 4.1 [TDD] 测 GET /api/task-records:分页+task_func/status 过滤,返回 {data,total,page,page_size};GET /api/task-records/<id> 返回单条(供前端轮询)
- [x] 4.2 [TDD] 测 DELETE /api/task-records:按 days 清理 N 天前且 status!=RUNNING 的记录,返回删除条数;RUNNING 不删
- [x] 4.3 [TDD] 测 /api/tasks 扩展:每个任务返回 running 字段(是否有 RUNNING 记录),供前端"执行中"列
- [x] 4.4 实现 api_server.py 新增 /api/task-records(列表,参照 /api/logs 分页模式)+ /api/task-records/<id>(单条)+ DELETE /api/task-records(参照 system_log 清理);web 直读 TaskRunRecordStorage,不转发 scheduler
- [x] 4.5 实现 /api/tasks 扩展:返回每个任务的 running 状态(查 get_running_record_by_func)
- [x] 4.6 跑 `python3 -m pytest tests/test_task_execution_tracking.py -q` 通过

### 5. 前端 TaskManage 改造(两列 + 异步执行 + 轮询 + 弹窗)
**Effort Estimate**: Large

#### Sub-tasks:
- [x] 5.1 `frontend/src/api/index.js`:taskApi 新增 getRunHistory(taskFunc,params)/getRunStatus(id)/cleanRunHistory(days);runTask 去掉 { timeout:120000 } 回落全局 10s
- [x] 5.2 TaskManage.vue 表格加"执行中"列:RUNNING 时 el-tag type=warning effect=dark 高亮"运行中";空闲 type=info 浅色"空闲"(对照 design 6.1)
- [x] 5.3 TaskManage.vue 表格加"执行计划"列:下划线链接形式(参照 SystemLog .log-message 样式:color #409eff + underline + hover #66b1ff),@click showHistoryDialog(row)
- [x] 5.4 runTask 函数(266-278)改异步:confirm -> POST /api/task/run -> 立即 ElMessage.success("任务已触发") 不 await 阻塞;遇 rejected 返回时 ElMessage.warning("任务正在运行，请等待完成")
- [x] 5.5 引入轮询:onMounted setInterval(fetchTasks,5000) + onBeforeUnmount clearInterval(参照 useEChart.js 清理范式,全项目首例)
- [x] 5.6 执行记录弹窗:el-dialog(800px,参照自有新增/编辑弹窗+SystemLog详情弹窗)+ 内嵌 el-table + el-pagination;列 ID/状态tag/触发类型/耗时(ms->秒)/开始/结束/trace_id(可复制,参照 trace-id-copy 样式)
- [x] 5.7 状态 tag 映射(参照 FundBuyer statusMap):RUNNING->warning 运行中/SUCCESS->success 已完成/FAILED->danger 失败/SKIPPED->info 已跳过
- [x] 5.8 弹窗顶部"清理历史记录"按钮(danger,弹确认框输保留天数,参照 SystemLog handleClean)
- [x] 5.9 对照 `tasks/design-task-execution-tracking.md` 第 6 节前端设计规范逐条核对
- [x] 5.10 前端构建门禁:`cd frontend && npm run build`,dist/ 随提交

### 6. 集成验证与全量回归
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 6.1 端到端验证:手动触发长任务(fetch_fund_detail_task)立即返回 triggered(0秒 vs 旧65秒),前端 5s 内显示"运行中",完成后变 SUCCESS(21秒耗时),弹窗看记录+trace_id;再触发遇 RUNNING 返回 rejected 不记表
- [x] 6.2 端到端验证 cron 路径记录:cron 触发的 update_fund_net_values_task 走 execute_task_with_record,记录 SUCCESS+耗时(12.6秒)
- [x] 6.3 `data-crawler/` 下跑 `python3 -m pytest tests/ -q` 全量回归(191 passed),确认无回归
- [x] 6.4 Phase 6 reviewer:同步起 2 个 code-reviewer agent(大改),已修复 3 高危(force_run 透传/409 改 200/启动重置僵尸RUNNING)+ 中危5(参数顺序)+ 低危8/9/11;中危4(TOCTOU)记为已知风险
- [x] 6.5 对照 `tasks/prd-task-execution-tracking.md` 验收标准 AC1-AC17 逐条核对(全部达标)

## Notes

### 依赖顺序
- 任务 1(表+Storage)是基础,任务 2/3/4 都依赖它。
- 任务 2(状态机包装器)依赖任务 1。
- 任务 3(异步改造)依赖任务 2(execute_task_with_record)。
- 任务 4(API)依赖任务 1(Storage)。
- 任务 5(前端)依赖任务 3/4(后端接口就绪)。
- 任务 6(集成验证)依赖全部。

### TDD 节奏(强制)
每个任务按:先写测试用例(明确预期与边界)-> 再写实现 -> `python3 -m pytest tests/test_task_execution_tracking.py -q` 通过 -> 勾选。禁止先实现后补测试。

### 关键约束
- **cron 防重叠所有任务都做**(短任务也多一次 DB 查询,任务少可接受)。
- **手动遇 RUNNING 不触发不记表**,只返回 rejected 让前端弹框提示。
- **cron 遇 RUNNING 记 SKIPPED**(审计可见)。
- **异步只改手动路径**,cron 路径保持同步(加重叠检查)。
- **前端构建门禁**:改 frontend/src/ 后 push 前 `npm run build` 并提交 dist/。
- **run_with_trace_context 兼容**:支持外部 trace_id,保留无 trace_id 自动生成(不破坏现有调用)。

### 首要风险
- 后台线程异常未 UPDATE 导致记录卡 RUNNING:execute_task_with_record 用 try/finally 保证;_run_task_in_thread 同样。
- 进程重启卡 RUNNING:本期靠清理接口手动处理(清理跳过 RUNNING 不删);后续可加启动时重置逻辑(design 第 8 节)。
- 轮询是全项目首例:务必 onBeforeUnmount clearInterval 防泄漏。

### 数据库部署
- task_run_record 表首次部署:`sql/alter/create_task_run_record_table.sql` 在生产库执行(或在 docs/deployment.md 补一句)。
