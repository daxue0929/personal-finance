# PRD — 指数基础表（index-basic-table）

**Feature slug**: `index-basic-table`
**前置依赖**：`unified-index-fetch-task` 已上线（PR `8d939f2` 合并），指数抓取已统一为 `fetch_index_task(index_code, market, force_run)`。

---

## 1. 背景

PR `8d939f2`「指数抓取任务统一重构」把 4 个独立任务合并为 `fetch_index_task`，但仍有两个未解的耦合点：

1. **指数元信息仍硬编码**：`data-crawler/app/parser/kc_index_parser.py` 的 `INDEX_NAME_MAP` 把 4 支指数的 `index_code → index_name` 写在 Python 源码里；新增一支指数要改代码 → 重新部署 → 还要在生产 `task_schedule` 插一行。
2. **task_schedule 行数与指数数量强耦合**：4 支指数 = 4 条任务记录，扩展到 10 支就 10 条；运维每次新增指数都要同时改 `task_schedule` 和代码（名字映射）。

**暴露的 bug**（2026-08-05 起）：8d939f2 把 `KcIndexParser.__init__` 里 `self.index_name = ''` 改成空串（注释说「名称由 DB 维护」），storage `create_or_update_index_info` 的 **insert 分支**直接把入参空串写入 `index_info.index_name`、**update 分支不刷新** 该字段。后续已临时修过 parser（加 `INDEX_NAME_MAP.get(index_code, '')` 兜底），但 storage 侧**仍缺一道 DB 元表兜底**——只要 `index_basic` 不存在，storage 拿不到 name，insert 出去的还是空。8月5、8月6 的 `index_info` 行 `index_name` 为 NULL（前端展示丢失中文名）。

本 PRD 目标：**用一张 `index_basic` 元表 + 单条统一抓取任务，彻底解耦「指数元信息维护」与「代码发布」**，并顺带修复上述中文名丢失问题。

---

## 2. 功能目标

| # | 目标 | 衡量方式 |
|---|------|----------|
| G1 | 指数元信息（代码/市场/名称/类型/启用）落库，可通过 API/UI 增删改查 | `index_basic` 表存在；CRUD 5 个接口全通；前端管理页可操作 |
| G2 | 抓取任务从 `index_basic` 动态读取 `enabled=1` 的指数列表，单条任务覆盖所有指数 | `task_schedule` 仅 1 条 `fetch_all_indexes_task`；新增指数**不改代码**只改 DB |
| G3 | 抓取时优先从 `index_basic.index_name` 取名字；`INDEX_NAME_MAP` 降级为兜底；老 `index_info` 历史不动 | 8月5/8月6 的空 name 被新抓取自动补齐；UI 改 name 不回写历史 |
| G4 | 4 条老的 `fetch_index_task` 任务记录在生产被禁用（`enabled=0`），保留可回滚 | 启动后 `task_schedule` 中老 4 条 `enabled=0`，新 1 条 `enabled=1` |
| G5 | 启用/停用某指数立即生效（无需重启 scheduler） | 停用后再触发定时任务，被禁用的 code 不再被拉取 |

---

## 3. 用户故事

- **US1 运维**：管理员登录后访问"指数基础"管理页，可看到所有指数（含停用的）、新增一支新指数（填代码+市场+名称+类型）、编辑名称、停用/启用、删除某支。整个过程**不碰 Python 代码、不重启服务**。
- **US2 调度**：scheduler 触发 `fetch_all_indexes_task` 时，自动从 `index_basic` 读 `enabled=1` 的全部行，循环抓取。停用的指数不抓、删除的（`del_flag=0`）不抓、market 非法或网络异常的指数 try/except 隔离，单支失败不影响其他。
- **US3 抓取名字**：抓取时优先用 `index_basic.index_name`（DB 真源），parser 的 `INDEX_NAME_MAP` 留作兜底；老 `index_info` 历史 name 保持不变（不级联更新）。
- **US4 回滚**：上线后发现新方案有 bug，把 4 条老任务记录从 `enabled=0` 改回 `enabled=1`，把新 `fetch_all_indexes_task` 改 `enabled=0`，即可回到原状态（保留记录便于回滚）。

---

## 4. 验收标准

### AC-1 SQL 变更

- [ ] 新建 `sql/alter/06_create_index_basic.sql`（沿用项目 2 位数序号惯例 + 简述命名），内容：
  - `CREATE TABLE index_basic` 字段：`index_code VARCHAR(6) PK`、`market VARCHAR(4) NOT NULL`、`index_name VARCHAR(64) NOT NULL`、`index_type VARCHAR(20) NOT NULL DEFAULT '宽基指数'`、`enabled TINYINT(1) NOT NULL DEFAULT 1`、`del_flag CHAR(1) NOT NULL DEFAULT '1'`、`create_by VARCHAR(64) DEFAULT NULL`、`create_time DATETIME DEFAULT NULL`、`update_by VARCHAR(64) DEFAULT NULL`、`update_time DATETIME DEFAULT NULL`。
  - 引擎 `InnoDB`、字符集 `utf8mb4`、排序 **`utf8mb4_general_ci`**（与项目其他 13 张 `sql/struct/*.sql` 保持一致；不要用 `_unicode_ci`）。
  - **不**加物理外键（项目惯例 `app/storage/index_info_storage.py` 注释 + CLAUDE.md「无物理外键约束」）。
  - 末尾 `INSERT INTO index_basic` 4 条初始数据：
    - `('000300', 'sh', '沪深300', '宽基指数', 1)`
    - `('000688', 'sh', '科创50', '宽基指数', 1)`
    - `('000698', 'sh', '科创100', '宽基指数', 1)`
    - `('399673', 'sz', '创业板50', '宽基指数', 1)`
- [ ] 新建 `sql/alter/07_migrate_index_tasks_to_unified_loop.sql`（或合并到 06，看实现便利）：
  - `INSERT INTO task_schedule (task_func, cron_expression, enabled, ...) VALUES ('fetch_all_indexes_task', '0 9 * * 1-5', 1, ...)`（与老 4 条同 cron 时间，**只跑一次**）。
  - `UPDATE task_schedule SET enabled=0 WHERE task_func LIKE 'fetch_index_task_%'`（禁用老的 4 条任务记录）。注意：8d939f2 重构后，4 条老任务在 `register_task.py` 用 `INDEX_TASK_REGISTRY` 字典 + `make_wrapper(code, market)` 闭包**动态注册**为 `fetch_index_task_000688` / `_000698` / `_000300` / `_399673` 4 个不同名（`task_schedule.task_func` 列也是这 4 个名字）。**不是**字面的 `fetch_index_task`。
  - 不删除老记录，保留可回滚。

### AC-2 后端 Storage

- [ ] 新建 `data-crawler/app/storage/index_basic_storage.py`，定义 ORM 类 `IndexBasic(Base)` + `IndexBasicStorage(StorageBase)`：
  - 列表查询 `list_all(include_disabled=False)`：`include_disabled=False` 时 `enabled=1 AND del_flag='1'`；True 时 `del_flag='1'` 全量。按 `index_code ASC` 排序。
  - 单条 `get(index_code)`：按主键查。
  - 增 `create(data)` / 改 `update(index_code, data)` / 软删 `soft_delete(index_code)`（置 `del_flag='0'`，不删 `index_info`）/ 启停 `toggle_enabled(index_code, enabled: bool)`。
  - 抓取用 `list_enabled()`：返回 `enabled=1 AND del_flag='1'` 的 `[(index_code, market, index_name), ...]`。
  - 字段白名单：`index_code, market, index_name, index_type, enabled`；`index_code` 不可改（主键）。
  - 验证：`market in ('sh', 'sz')`，`index_code` 长度 6 且全数字；验证失败 raise `ValueError`，被 `@log_request` 装饰器捕获记录。
- [ ] 在 `data-crawler/app/storage/__init__.py` 导出 `IndexBasicStorage`。
- [ ] `app/storage/index_info_storage.py` 的 `create_or_update_index_info` insert 分支：`index_name` 兜底顺序（按优先级）——`index_data.index_name` → `index_basic.index_name`（DB 真源）→ `INDEX_NAME_MAP[code]`（parser 兜底）→ `index_info` 自身历史最近一条非空 name（**保留原有兜底**，不删）→ `''`。每道独立 try/except 隔离，失败降级到下一道。
- [ ] `app/parser/kc_index_parser.py` 保留 `INDEX_NAME_MAP` 作为**最终兜底**（不删），注释从「名称由 DB 维护，不再硬编码」改为「DB 与 storage 优先；此为最终兜底，DB 未配且历史为空时使用」。

### AC-3 后端 Task

- [ ] 新建 `data-crawler/app/task/fetch_all_indexes_task.py`，定义 `fetch_all_indexes_task(force_run: bool = False) -> None`：
  - 从 `IndexBasicStorage.list_enabled()` 读全部 `enabled=1` 列表；若为空打 WARN 日志「无启用指数」并 return。
  - 用 `concurrent.futures.ThreadPoolExecutor(max_workers=4)` 并发抓取；每支起一个 future 调 `fetch_and_store_index_with_market(index_code, market, force_run)`。
  - 每个 future try/except 隔离，单支失败不影响其他；future 返回的 `KcIndexData` 通过 `as_completed` 收集。
  - **保留 kc100 副作用**（硬编码 + TODO 注释）：抓取完成收集到 `000698` 的 `change_percent` 时，调 `FundInfoStorage().update_fund_remark('020292', f"{change_percent:.2f}")`，异常 try/except 隔离。在文件顶部加注释：`# TODO: linked_fund_code / linked_field 字段后续加入 index_basic 后可数据驱动化；详见 PRD "index-basic-table" §5 非目标。`
- [ ] `data-crawler/app/task/register_task.py` 新增 1 行：`scheduler.register_task('fetch_all_indexes_task', fetch_all_indexes_task)`。**保留** `INDEX_TASK_REGISTRY` 字典 + 4 个 `fetch_index_task_<code>` wrapper 闭包——4 条老任务在 `task_schedule` 中 `enabled=0` 不再被调度，但通过 API `/api/task/run/<task_func>` 仍可手动触发，**作为回滚通道**。不删 wrapper。

### AC-4 后端 API

- [ ] `data-crawler/app/web/api_server.py` 新增 6 个路由，挂在 `/api/index-basics`：
  - `GET /api/index-basics?include_disabled=true|false` 列表（默认 false）。
  - `GET /api/index-basics/<index_code>` 详情。
  - `POST /api/index-basics` 新增；body `{index_code, market, index_name, index_type?, enabled?}`。
  - `PUT /api/index-basics/<index_code>` 改（`index_code` 不可改）；body 同上但 `index_code` 忽略。
  - `DELETE /api/index-basics/<index_code>` 软删（`del_flag='0'`）。
  - `POST /api/index-basics/<index_code>/toggle` body `{enabled: 0|1}` 启停。
  - 全部走 `@log_request` 装饰器；错误统一 try/except 返回 `{error: msg}` + 4xx/5xx。
  - 列表分页：`page`、`page_size`（默认 10/20/50/100），与项目其他列表接口一致。
- [ ] 字段白名单与 storage 一致；`index_code` 不可改（PUT 时白名单过滤）。

### AC-5 前端

- [ ] `frontend/src/views/IndexBasic.vue` 新页面：
  - 顶部 `<el-button>`「新增指数」打开 `<el-dialog>` 表单（code/market/name/type/enabled）。
  - 表格 `<el-table>` 列：`index_code, market, index_name, index_type, enabled, create_time, update_time, 操作`。
  - 操作列：「编辑」「停用/启用」「删除」三个 `<el-button>`，删除前 `ElMessageBox.confirm` 二次确认。
  - 顶部 `el-switch` 切换「显示已停用」（对应 `include_disabled=true`），关闭时只显示 `enabled=1`。
  - 表格分页 `el-pagination`。
- [ ] `frontend/src/api/index.js` 新增 `indexBasicApi`：
  - `list({ includeDisabled, page, pageSize })`
  - `get(code)`
  - `create(data)`
  - `update(code, data)`
  - `remove(code)`
  - `toggle(code, enabled)`
- [ ] `frontend/src/router/index.js` 重排 3 条路由 `meta.sort`：`/index/info` = 46（不变）、`/index/basic` = **47**（新增）、`/index/analysis` = **48**（从 47 调上来）。新增 `/index-basic` 路由，指向 `IndexBasic.vue`，label「指数基础」。
- [ ] `frontend/src/components/Layout.vue`（项目**无独立 Sidebar.vue**，菜单/图标/路由都内联在此组件）：在第 75 行 `import` 列表追加新图标（如 `Collection`）；在第 116-134 行 `iconMap` 增加 `/index/basic` → 新图标的映射。

### AC-6 测试

- [ ] `data-crawler/tests/test_index_basic_storage.py`（TDD 先写）：
  - `test_list_enabled_only_returns_enabled`：fixture 种 3 条 enabled=1 + 1 条 enabled=0，`list_enabled()` 返 3 条。
  - `test_list_include_disabled_returns_all`：同上，`list_all(include_disabled=True)` 返 4 条。
  - `test_create_validates_market`：create `market='xx'` → ValueError。
  - `test_create_validates_index_code_length`：create `index_code='12345'` → ValueError。
  - `test_soft_delete_keeps_row`：`soft_delete('000300')` 后行仍在但 `del_flag='0'`；`list_enabled()` 不返。
  - `test_toggle_enabled_changes_flag`：`toggle_enabled('000300', 0)` 后 `list_enabled` 不含。
  - `test_get_returns_none_for_missing`：`get('999999')` 返 None。
- [ ] `data-crawler/tests/test_index_basic_api.py`：
  - `test_list_endpoint_returns_enabled_by_default`（mock storage）
  - `test_create_endpoint_rejects_invalid_market` → 400
  - `test_toggle_endpoint_updates_enabled`
  - `test_delete_endpoint_calls_soft_delete`
- [ ] `data-crawler/tests/test_fetch_all_indexes_task.py`：
  - `test_no_enabled_indexes_logs_and_returns`：mock storage `list_enabled()=[]`，打 WARN 并 return。
  - `test_concurrent_fetch_uses_threadpool`（mock）：4 支指数时 ThreadPoolExecutor 收到 4 个 future。
  - `test_single_failure_does_not_block_others`：mock 一支抛异常，其余 3 支正常完成。
  - `test_kc100_side_effect_runs_after_concurrent`（mock）：000698 抓取结果后调 `FundInfoStorage.update_fund_remark('020292', '<change_pct>')`。
  - `test_kc100_side_effect_swallows_exception`。
- [ ] 现有测试（`test_unified_index_fetch_task.py` 等）保持通过。
- [ ] `data-crawler/tests/test_index_info_storage_name_fallback.py`（新增或合并到 `test_index_info_storage.py`）：覆盖 4 道 name 兜底优先级——`index_data` > `index_basic` > `INDEX_NAME_MAP` > 历史 `index_info` > 空。

### AC-7 全量回归

- [ ] `cd data-crawler && python3 -m pytest tests/ -q` 全量通过。
- [ ] `cd frontend && npm run build` 成功。
- [ ] 启动后 `task_schedule` 表状态：
  - `SELECT task_func, COUNT(*), SUM(enabled) FROM task_schedule GROUP BY task_func;` 应看到：`fetch_index_task` 4 条全 `enabled=0`；`fetch_all_indexes_task` 1 条 `enabled=1`。
- [ ] 启动后 `index_basic` 表存在且含 4 条初始数据。
- [ ] 手动触发 `fetch_all_indexes_task` 一次：拉取日志显示 4 支指数全部 OK；`index_info` 表当天/次日新行 `index_name` 非空。
- [ ] `frontend/src/views/IndexInfo.vue` 第 64 行 `index_name` 列兜底：`<el-table-column prop="index_name">` 改为带 `<template #default="{ row }">{{ row.index_name || '—' }}</template>`。**顺手小改**，避免 8月5/6 历史空名行显示为空白单元格。（scope +1 行，npm run build 必跑）

---

## 5. 非目标

- **不**做 `linked_fund_code` 字段（020292 联动）数据驱动化——本期维持硬编码 + TODO 注释。
- **不**做「改 index_basic.index_name 时级联 UPDATE 历史 index_info」——历史 name 保持不变。
- **不**做指数基础数据的导入/导出（CSV、Excel）。
- **不**加权限/审计（项目单用户设计）。
- **不**做 K 线/分时等其他行情类型（仍只日线 OHLCV）。
- **不**改 `KcIndexParser` 的字段解析逻辑（parts 下标、PE/PB 位置）。
- **不**改 `task_schedule.func_args` 机制——新任务不带参数（参数从 DB 读）。
- **不**改前端「指数分析」页（`IndexAnalysis.vue`）的图表——它继续从 `index_info` 读，写入侧本表维护，名字问题随 AC-2 storage 兜底 + 新抓取自动修复。
- **不**做索引（`INDEX`）优化——初期数据量小（<100 条），`index_code` 已是 PK，无需额外索引。

---

## 6. 依赖

- PR `8d939f2`（`unified-index-fetch-task`）已合并；`task_schedule.func_args` 列已存在。
- 现有 `app/storage/index_info_storage.py`、`app/parser/kc_index_parser.py` 的现有逻辑可复用。
- `app/utils/thread_pool_executor.py` 或 `concurrent.futures` 标准库（无第三方依赖）。
- 前端 Element Plus 已有 `el-table` / `el-dialog` / `el-form` / `el-switch` / `el-pagination` 组件（已在 FundManage.vue 等使用过）。
- MySQL 8.x；`utf8mb4_unicode_ci` 与项目其他表一致。

---

## 7. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 并发抓取时 000698 副作用被多线程竞争 | `update_fund_remark` 被覆盖或重复写 | 用 `as_completed` 顺序收集 future；000698 副作用在所有 future 完成后**单线程串行**触发一次 |
| ThreadPoolExecutor 默认 daemon + 异常未捕获 → 任务静默失败 | 单支抓取失败无日志 | 每个 future 内 `try/except Exception as e: logger.error(...)` + return None；主路径 `wait(futures)` 后再处理副作用 |
| 4 条老任务 `enabled=0` 后忘记迁移 → 抓取中断 | 4 支指数停止抓取 | AC-7 显式验收：启动后 SQL 校验 `SUM(enabled) WHERE task_func IN ('fetch_index_task', 'fetch_all_indexes_task')` 至少为 1；部署文档加自检步骤 |
| `index_basic` 表上线但 4 条初始 INSERT 失败 → scheduler 启动后无指数可抓 | 抓取空跑 | AC-1 一次性脚本 + 部署文档提示执行顺序「先建表 + 插 4 条，再启 scheduler」；启动日志中 `fetch_all_indexes_task` 执行时 list_enabled() 为空打 WARN |
| 多线程抓取时网络请求同时打腾讯被限流 | 单支抓取失败 | 4 个并发对腾讯接口压力可忽略（实测 4 支 ≤2s 完成）；如未来扩到 20+ 支再降回顺序 |
| 软删某指数后 `index_info` 历史保留，但前端分析页会展示「该指数无最新数据」 | UI 显示困惑 | 分析页本身按 `index_info` 查，与 `index_basic.del_flag` 无关；如需联动在 `IndexAnalysis.vue` 加过滤（**非目标**，本期不动） |
| 前端表单误填 `market='shanghai'` 而不是 `'sh'` | 抓取任务 ValueError | AC-2 storage 验证 + AC-6 测试覆盖；前端 `<el-select>` 限定选项 `'sh' \| 'sz'` |
| 删除某指数时若有 `index_info` 引用（无外键），后续分析页空 name | UI 体验差但不报错 | 项目无外键是惯例；如未来需要硬删保护，单独迭代 |
| `index_basic` 与 `task_schedule` 的迁移顺序在生产与本地不一致 | 启动后状态混乱 | 文档化部署步骤；DBA 手动跑 SQL（不靠代码自动迁移） |

---

## 8. Open Questions

（已与用户澄清完，无遗留）

历史决策记录（实现时如发现冲突，优先按此表）：
- 字符集：与项目保持 `utf8mb4_general_ci`（非 `_unicode_ci`）。
- `task_func` 命名：4 条老任务是 `fetch_index_task_<code>` 闭包 wrapper，不是字面 `fetch_index_task`；SQL 用 `LIKE 'fetch_index_task_%'`。
- name 兜底顺序：4 道，独立 try/except。
- `INDEX_TASK_REGISTRY` wrapper：保留作回滚通道。
- 路由 sort：重排为 46/47/48（Info=46、Basic=47、Analysis=48）。
- 菜单注册：直接改 `Layout.vue`，不新建 `Sidebar.vue`。
- IndexInfo.vue 空 name：顺手加 `row.index_name || '—'` 兜底。

---

## 9. 实施顺序（粗）

1. **SQL**：`sql/alter/06_create_index_basic.sql`（建表 + 初始 4 条）；`sql/alter/07_migrate_index_tasks.sql`（新增 fetch_all_indexes_task + 禁用老 4 条）。
2. **后端 Storage**：`storage/index_basic_storage.py` + `storage/__init__.py` 导出 + `storage/index_info_storage.py` insert 分支加 DB 兜底。
3. **后端 Task**：`task/fetch_all_indexes_task.py`（含 ThreadPool + kc100 副作用 + TODO 注释）+ `task/register_task.py` 新增注册。
4. **后端 API**：`web/api_server.py` 6 个路由。
5. **后端测试**：先写 `test_index_basic_storage.py` / `test_index_basic_api.py` / `test_fetch_all_indexes_task.py`，TDD 通过后再合实现。
6. **前端 API**：`api/index.js` 新增 `indexBasicApi`。
7. **前端页面**：`views/IndexBasic.vue` + `router/index.js` 注册 + 侧边菜单。
8. **全量回归**：`pytest tests/ -q` + `npm run build` + 手动触发 `fetch_all_indexes_task` 验证。
9. **部署文档**（可选）：在 `docs/deployment.md` 追加本功能部署步骤（DBA 跑 SQL 顺序、回滚命令）。
