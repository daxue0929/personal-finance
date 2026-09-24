# Design: 任务执行记录与状态追踪(task-execution-tracking)

**Feature slug**: `task-execution-tracking`

> 架构 + 前端设计规范。配套 PRD 见 `tasks/prd-task-execution-tracking.md`。

## 1. 设计约束(已与用户锁定)

- 新建 `task_run_record` 表,每次执行有记录+状态;状态机 RUNNING/SUCCESS/FAILED/SKIPPED。
- 异步触发:手动点"执行"立即返回"已触发",前端轮询;cron 路径保持同步(APScheduler 线程池)。
- cron 防重叠:所有任务触发前查 DB,RUNNING 则跳过记 SKIPPED(跨重启/跨手动,DB 级)。
- 手动触发遇 RUNNING:拒绝提示,不叠加。
- 执行记录:TaskManage 页内弹窗(不新建页面)。
- 状态轮询:setInterval 每 5s 刷新任务列表,onUnmounted 清理。
- 历史清理:提供清理接口(前端按钮)。
- 通用:未来更多长耗时任务复用,任务函数本身不动,只加包装器。
- trace_id 复用:执行记录与 system_log 同 trace_id,可串联跳转。

## 2. 整体架构

```
┌─────────────── 前端 TaskManage.vue ───────────────┐
│ 表格新增两列:[执行计划]按钮 / [执行中]tag         │
│   ├─ 点"执行":POST /api/task/run -> 立即提示已触发 │
│   ├─ setInterval 5s 轮询 /api/tasks(含 running)   │
│   └─ 点"执行计划":弹窗 GET /api/task-records       │
└───────────────────────┬───────────────────────────┘
                        │
┌─────────────── web 进程(直读 Storage)─────────────┐
│ POST /api/task/run/<func>  -> 转发 scheduler(异步) │
│ GET  /api/tasks            -> 扩展返回 running 状态 │
│ GET  /api/task-records     -> 分页查历史(直读DB)    │
│ GET  /api/task-records/<id>-> 单条状态轮询(直读DB)  │
│ DELETE /api/task-records   -> 清理N天前(直读DB)     │
└───────────────────────┬───────────────────────────┘
                        │ /internal/task/run(立即返回)
┌─────────────── scheduler 进程 ────────────────────┐
│ run_job_now: INSERT RUNNING + 起后台线程 -> 立即返  │
│ cron wrapped_func: execute_task_with_record        │
│   ├─ 重叠检查(SELECT RUNNING) -> SKIPPED return    │
│   ├─ INSERT RUNNING(trace_id)                       │
│   ├─ run_with_trace_context(task_func)              │
│   └─ finally: UPDATE SUCCESS/FAILED(耗时/错误)      │
└───────────────────────┬───────────────────────────┘
                        │
┌─────────────── task_run_record 表 ────────────────┐
│ id/task_func/task_name/trigger_type/status/         │
│ trace_id/triggered_by/start_time/end_time/          │
│ duration_ms/error_message/create_time/update_time   │
│ idx_task_func_status / idx_task_func_start / idx_trace_id │
└────────────────────────────────────────────────────┘
```

## 3. 数据库设计(task_run_record)

参照 `position_daily_snapshot.sql` 新风格 + `task_schedule.sql` 审计字段。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint PK auto | 主键 |
| task_func | varchar(200) NOT NULL | 任务函数名(关联 task_schedule.task_func) |
| task_name | varchar(100) | 任务名(冗余,便于展示) |
| trigger_type | varchar(20) NOT NULL | `cron` / `manual` |
| status | varchar(20) NOT NULL | `RUNNING` / `SUCCESS` / `FAILED` / `SKIPPED` |
| trace_id | varchar(64) | 链路 ID,关联 system_log.trace_id |
| triggered_by | varchar(64) | `scheduler`(cron) / 用户名(manual) |
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |
| duration_ms | int | 耗时毫秒 |
| error_message | text | 失败错误信息 |
| create_time / update_time | datetime | 审计 |

索引:`idx_task_func_status(task_func, status)`(防重叠查询)、`idx_task_func_start(task_func, start_time)`(历史查询)、`idx_trace_id`。无 del_flag(执行记录是流水,不软删,靠清理接口)。

**IDLE 为派生态**:某 task_func 当前无 status='RUNNING' 的记录即 IDLE,不单独存。

## 4. 状态机与执行包装

### 4.1 execute_task_with_record(cron 路径,同步)

```python
def execute_task_with_record(self, task_func, task_name, trigger_type='cron', triggered_by='scheduler'):
    # 1. 防重叠:查 RUNNING
    if self._run_record_storage.get_running_record_by_func(task_func):
        self._run_record_storage.create_record(task_func, task_name, trigger_type,
                                                status='SKIPPED', triggered_by=triggered_by,
                                                start_time=now, end_time=now, duration_ms=0)
        logger.info(f"任务 {task_func} 已在运行，跳过本次")
        return
    # 2. INSERT RUNNING(生成 trace_id)
    trace_id = str(uuid.uuid4())
    record = self._run_record_storage.create_running_record(task_func, task_name, trigger_type,
                                                            trace_id, triggered_by)
    # 3. 跑任务(trace_id 注入 ContextVar)
    start = time.time()
    try:
        run_with_trace_context(self.task_registry[task_func], task_name, trace_id=trace_id)
        status, err = 'SUCCESS', None
    except Exception as e:
        status, err = 'FAILED', str(e)
    finally:
        duration = int((time.time()-start)*1000)
        self._run_record_storage.update_record_status(record.id, status, end_time=now,
                                                      duration_ms=duration, error_message=err)
```

- cron 路径(`_add_job` 的 wrapped_func)调此方法。
- `run_with_trace_context` 需支持传入外部 trace_id(复用记录的 trace_id),保证日志串联。

### 4.2 run_job_now(手动路径,异步)

```python
def run_job_now(self, task_func_name, force_run=False, triggered_by='manual'):
    if task_func_name not in self.task_registry:
        return False
    # 防重叠:手动触发遇 RUNNING -> 不触发、不记表、返回 rejected 让前端弹框提示
    if self._run_record_storage.get_running_record_by_func(task_func_name):
        return {'rejected': True, 'message': '任务正在运行，请等待完成'}
    # INSERT RUNNING
    trace_id = str(uuid.uuid4())
    record = self._run_record_storage.create_running_record(...)
    # 起后台线程跑
    threading.Thread(target=self._run_task_in_thread, args=(task_func_name, record, trace_id), daemon=True).start()
    return {'record_id': record.id, 'trace_id': trace_id}  # 立即返回
```

- `_run_task_in_thread`:线程内 run_with_trace_context + finally UPDATE,复用 trace_id。
- **手动遇 RUNNING 不记表**:不写 SKIPPED,仅返回 rejected 标志,前端弹框提示用户等待。

## 5. 改动文件清单

### 新建
- `sql/struct/task_run_record.sql` - 表结构(DROP+CREATE,全新建库用)
- `sql/alter/create_task_run_record_table.sql` - 生产增量(CREATE TABLE IF NOT EXISTS)
- `data-crawler/app/storage/task_run_record_storage.py` - TaskRunRecord 模型 + Storage
- `data-crawler/tests/test_task_execution_tracking.py` - TDD 测试

### 修改(后端)
- `app/storage/__init__.py` - 导出 TaskRunRecord/Storage
- `app/scheduler/cron_scheduler.py` - execute_task_with_record + run_job_now 异步 + _add_job 用包装器 + run_with_trace_context 支持外部 trace_id
- `app/scheduler/control_server.py` - /internal/task/run 立即返回 triggered+record_id+trace_id
- `app/web/scheduler_proxy.py` - run_task 超时降为 CTRL_TIMEOUT
- `app/web/api_server.py` - /api/task/run 返回 triggered + 新增 /api/task-records(列表/单条/清理)+ /api/tasks 扩展 running 状态

### 修改(前端)
- `frontend/src/api/index.js` - taskApi 新增 getRunHistory/getRunStatus/cleanRunHistory;runTask 去掉 120s 超时
- `frontend/src/views/TaskManage.vue` - 加两列 + 异步执行 + 5s 轮询 + 执行记录弹窗 + 清理按钮

## 6. 前端设计规范

> 参照现有设计系统(SystemLog.vue / FundBuyer.vue / TaskManage.vue 自身),不引入新设计语言。

### 6.1 新增两列(TaskManage 表格)
- **执行中**列:RUNNING 时**高亮突出显示**--el-tag 用 `type="warning" effect="dark"`(深色实心,区别于普通浅色 tag),文案"运行中";无 RUNNING 时弱化显示,`type="info"`(浅色)+ "空闲"。高亮使用户一眼看到正在跑的任务。
- **执行计划**列:**下划线 + 可点击**的链接形式(非按钮),文案"执行计划",`@click="showHistoryDialog(row)"`。样式参照 SystemLog.vue 的 `.log-message`(color:#409eff + cursor:pointer + text-decoration:underline),hover 加深(`#66b1ff`)。

### 6.2 执行记录弹窗
- el-dialog,标题"执行记录 - {task_name}",宽度 800px。参照 TaskManage 自有新增/编辑弹窗(74-103 行)+ SystemLog 详情弹窗(109-128 行)。
- 内嵌 el-table + el-pagination(参照 SystemLog 表格+分页)。
- 列:ID / 状态(tag) / 触发类型(cron/manual) / 耗时(ms->秒) / 开始时间 / 结束时间 / trace_id(可复制,参照 SystemLog trace-id-copy 样式)。
- 状态 tag 映射:RUNNING->warning 运行中 / SUCCESS->success 已完成 / FAILED->danger 失败 / SKIPPED->info 已跳过。
- 顶部"清理历史记录"按钮(danger 类型,弹确认框输保留天数,参照 SystemLog handleClean)。

### 6.3 异步执行交互
- 点"执行":confirm -> POST /api/task/run -> 立即 ElMessage.success("任务已触发") -> 不 await 阻塞 -> 触发后下次轮询(5s 内)刷新出"运行中"tag。
- runTask API 去掉 `{ timeout: 120000 }`,回落全局 10s(触发指令是轻量短请求)。

### 6.4 轮询机制(全项目首例)
- `onMounted` 启动 `setInterval(fetchTasks, 5000)`,`onUnmounted`/`onBeforeUnmount` `clearInterval`。参照 useEChart.js(28 行)的清理范式防泄漏。
- fetchTasks 复用现有任务列表查询(扩展返回 running 状态)。
- 轮询仅在 TaskManage 页面激活时进行,离开页面清除。

## 7. 关键决策记录

- **状态用记录表而非 task_schedule 加列**:避免 cron/手动并发改同一行、避免进程重启丢内存状态,且天然有完整执行历史。
- **IDLE 为派生态**(无 RUNNING 记录即 IDLE),不单独存。
- **防重叠查 DB**(WHERE task_func=? AND status='RUNNING')而非 APScheduler max_instances:跨重启、跨手动/cron、可审计。
- **异步只改手动路径**:cron 路径 APScheduler 已在线程池跑,保持同步加重叠检查,不引入额外线程。
- **trace_id 复用**:记录表 trace_id 与 system_log 同值,弹窗 trace_id 可复制,日志页按 trace_id 过滤看本次执行日志。
- **手动触发遇 RUNNING 不触发不记表**:不写 SKIPPED、不起线程,仅返回 rejected 标志,前端弹框提示用户等待。与 cron 的 SKIPPED(审计可见)区分--手动是用户主动行为,提示即可,无需留痕。

## 8. 待定/后续

- **TOCTOU 竞态(中危,已知风险)**:防重叠是应用层 check-then-act(`get_running_record_by_func` 查无 -> `create_running_record` INSERT),无原子保证。cron 与手动同时触发同一任务的窗口极小(需在毫秒级同时查到无 RUNNING 再各自 INSERT),本期接受此风险。后续可改用 MySQL 生成列 + 唯一约束(`is_running BOOL AS (status='RUNNING') STORED` + `UNIQUE(task_func, is_running)`)实现真正 DB 级原子防重叠,create_running_record 捕获 IntegrityError 返回 None,调用方判断。
- **进程重启卡 RUNNING(已修复)**:启动时 `reset_stale_running(threshold=60min)` 把超时 RUNNING 置 FAILED,避免崩溃后任务永久 SKIPPED。
- **轮询频率 5s 可调**,后续若任务多可优化为仅轮询有 RUNNING 的任务。
