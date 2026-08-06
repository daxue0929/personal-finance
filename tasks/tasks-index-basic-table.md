# Task List: 指数基础表（index-basic-table）

**基于 PRD**：`tasks/prd-index-basic-table.md`
**配套 Design**：`tasks/design-index-basic-table.md`
**实施日期**：待开始
**总估算**：Medium-Large（5-7 个工作日）

---

## Relevant Files

### Files to Create

**SQL 层**
- `sql/alter/06_create_index_basic.sql` — 建表 + 初始 4 条 INSERT
- `sql/alter/07_migrate_index_tasks_to_loop.sql` — 新增 fetch_all_indexes_task + 禁用老 4 条

**后端 Storage / Task / API**
- `data-crawler/app/storage/index_basic_storage.py` — IndexBasic ORM + IndexBasicStorage CRUD
- `data-crawler/app/task/fetch_all_indexes_task.py` — 统一遍历抓取任务（ThreadPool）

**后端测试**
- `data-crawler/tests/test_index_basic_storage.py` — Storage CRUD + 验证测试
- `data-crawler/tests/test_index_basic_api.py` — 6 路由 mock 测试
- `data-crawler/tests/test_fetch_all_indexes_task.py` — 并发 + kc100 副作用测试
- `data-crawler/tests/test_index_info_storage_name_fallback.py` — 4 道 name 兜底优先级测试

**前端**
- `frontend/src/views/IndexBasic.vue` — 指数基础 CRUD 页面

### Files to Modify

**后端**
- `data-crawler/app/storage/__init__.py` — 导出 IndexBasicStorage
- `data-crawler/app/storage/index_info_storage.py` — `create_or_update_index_info` insert 分支加 4 道 name 兜底
- `data-crawler/app/task/register_task.py` — 新增 1 行 register `fetch_all_indexes_task`；保留 `INDEX_TASK_REGISTRY`
- `data-crawler/app/web/api_server.py` — 新增 6 路由 + 顶部 storage 单例

**前端**
- `frontend/src/api/index.js` — 新增 `indexBasicApi` 6 方法
- `frontend/src/router/index.js` — 重排 3 条 sort（46/47/48）+ 新增 `/index/basic` 路由
- `frontend/src/components/Layout.vue` — 第 75 行 import `Files` + iconMap 加 `/index/basic`
- `frontend/src/views/IndexInfo.vue` — 第 64 行 `index_name` 列加 `row.index_name || '—'` 兜底

### Documentation (Optional)
- `docs/deployment.md` — 追加 index-basic-table 部署步骤 + 回滚命令

---

## Implementation Tasks

### T1. SQL 变更

**Effort Estimate**: Small（1-2 小时）

#### Sub-tasks:

- [ ] **T1.1** 创建 `sql/alter/06_create_index_basic.sql` 骨架
  - 文件顶部 `SET NAMES utf8mb4;`
  - `CREATE TABLE index_basic` 字段：`index_code VARCHAR(6) PK`、`market VARCHAR(4) NOT NULL`、`index_name VARCHAR(64) NOT NULL`、`index_type VARCHAR(20) NOT NULL DEFAULT '宽基指数'`、`enabled TINYINT(1) NOT NULL DEFAULT 1`、`del_flag CHAR(1) NOT NULL DEFAULT '1'`、`create_by/update_by VARCHAR(64) DEFAULT NULL`、`create_time/update_time DATETIME DEFAULT NULL`
  - 引擎 `InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci`（**项目惯例，非 unicode_ci**）
  - 字段级 `COLLATE utf8mb4_general_ci` + COMMENT
  - 末尾 `SET FOREIGN_KEY_CHECKS = 1;`
  - 依赖：无
  - 验收：脚本可在测试库 `mysql -u root -p` 跑通；`DESCRIBE index_basic` 字段与上述一致

- [ ] **T1.2** 追加 4 条初始 INSERT（同文件末尾）
  - `INSERT INTO index_basic (index_code, market, index_name, index_type, enabled) VALUES`
  - `('000300', 'sh', '沪深300', '宽基指数', 1)`
  - `('000688', 'sh', '科创50', '宽基指数', 1)`
  - `('000698', 'sh', '科创100', '宽基指数', 1)`
  - `('399673', 'sz', '创业板50', '宽基指数', 1)`
  - 依赖：T1.1
  - 验收：跑完后 `SELECT * FROM index_basic` 返回 4 行

- [ ] **T1.3** 创建 `sql/alter/07_migrate_index_tasks_to_loop.sql`
  - `INSERT INTO task_schedule (task_func, task_name, cron_expression, enabled, del_flag, description, create_by, create_time, update_by, update_time) VALUES ('fetch_all_indexes_task', '统一指数抓取（全量遍历 index_basic）', '0 9 * * 1-5', 1, '1', '遍历 index_basic.enabled=1 全量拉取', 'crawler', NOW(), 'crawler', NOW());`（带 `ON DUPLICATE KEY UPDATE` 幂等）
  - `UPDATE task_schedule SET enabled=0, update_by='crawler', update_time=NOW() WHERE task_func LIKE 'fetch_index_task_%' AND enabled=1;`（**仅禁用在用的**，保留记录）
  - 末尾加 `= 验证 =` 注释 + 预期 `SELECT task_func, COUNT(*) AS rows, SUM(enabled) AS enabled_count FROM task_schedule WHERE task_func LIKE 'fetch_index_task_%' OR task_func='fetch_all_indexes_task' GROUP BY task_func;` 输出 5 行（4+1）
  - 依赖：无（与 T1.1/T1.2 独立）
  - 验收：DBA 手动跑后 `task_schedule` 中老 4 条 `enabled=0`、新 1 条 `enabled=1`

- [ ] **T1.4** SQL 脚本本地 dry-run
  - 拉一个测试库（`docker run -e MYSQL_ROOT_PASSWORD=test -p 3307:3306 mysql:8`）跑 T1.1 + T1.2 + T1.3
  - 跑完所有 `SHOW CREATE TABLE index_basic\G`、`SELECT * FROM index_basic`、`SELECT * FROM task_schedule` 截图存档
  - 依赖：T1.1, T1.2, T1.3
  - 验收：3 个表 dump 全部符合预期

**TDD 提示**：T1 全是 SQL 脚本，无 pytest。手动 dry-run 即可。

---

### T2. 后端 Storage 层

**Effort Estimate**: Medium（4-6 小时）

#### Sub-tasks:

- [ ] **T2.1** `storage/index_basic_storage.py` ORM 类 `IndexBasic(Base)`
  - `__tablename__ = 'index_basic'`
  - 9 个 Column 字段与 SQL T1.1 完全对应
  - 依赖：T1.1（表存在）
  - 验收：`python -c "from app.storage.index_basic_storage import IndexBasic; print(IndexBasic.__table__.columns.keys())"` 输出 9 个字段名

- [ ] **T2.2** `IndexBasicStorage(StorageBase)` 基础结构
  - `__init__` 调 `get_db_engine()` + `get_db_session`（参照 `fund_buyer_storage.py:106-130` 模式）
  - `get_session()` 方法
  - 继承 `StorageBase` 触发 `__init_subclass__` 自动加 `storage_log` 装饰器
  - 依赖：T2.1
  - 验收：`python -c "from app.storage.index_basic_storage import IndexBasicStorage; s = IndexBasicStorage(); print(s)"` 不报错

- [ ] **T2.3** 列表查询方法
  - `list_all(include_disabled=False) -> List[Dict]`：默认 `enabled=1 AND del_flag='1'`，True 时 `del_flag='1'`，按 `index_code ASC`
  - `list_enabled() -> List[Tuple[index_code, market, index_name]]`：抓取用，最小字段
  - `get(index_code) -> Optional[IndexBasic]`：按主键
  - 依赖：T2.2
  - 验收：T5.1 测试覆盖（`test_list_enabled_only_returns_enabled` / `test_list_include_disabled_returns_all`）

- [ ] **T2.4** `create(data) -> bool`
  - 验证：`market in ('sh', 'sz')` raise ValueError；`index_code` 长度 6 且 `isdigit()` 否则 raise ValueError
  - 字段白名单：`index_code, market, index_name, index_type, enabled`
  - `create_by='admin'` / `create_time=get_beijing_now()`
  - 已存在 raise `IntegrityError` 包装为 `ValueError("指数代码已存在")`
  - 依赖：T2.3
  - 验收：T5.1 `test_create_validates_market` / `test_create_validates_index_code_length` 通过

- [ ] **T2.5** `update(index_code, data) -> bool`
  - 验证 `index_code` 已存在（不在则 return False）
  - 字段白名单同上；`index_code` 不可改（白名单不含）
  - `update_by='admin'` / `update_time=get_beijing_now()`
  - 依赖：T2.4
  - 验收：T5.1 `test_update_changes_name_only` 通过

- [ ] **T2.6** 软删 + 启停
  - `soft_delete(index_code) -> bool`：置 `del_flag='0'`、`update_by='admin'`、`update_time=now()`；`index_info` 历史不动
  - `toggle_enabled(index_code, enabled: bool) -> bool`：更新 `enabled` 字段；值转 1/0
  - 依赖：T2.5
  - 验收：T5.1 `test_soft_delete_keeps_row` / `test_toggle_enabled_changes_flag` 通过

- [ ] **T2.7** `storage/__init__.py` 导出
  - `from .index_basic_storage import IndexBasicStorage` 加 1 行
  - `__all__` 列表追加 `'IndexBasicStorage'`
  - 依赖：T2.6
  - 验收：`python -c "from app.storage import IndexBasicStorage; print(IndexBasicStorage)"` 不报错

- [ ] **T2.8** `index_info_storage.py` insert 分支 4 道 name 兜底
  - 位置：`create_or_update_index_info` else 分支（line 224 附近）
  - 顺序：`index_data.index_name` → `IndexBasicStorage().get(index_code).index_name`（DB 真源）→ `KcIndexParser.INDEX_NAME_MAP.get(index_code, '')`（parser 兜底）→ `index_info` 自身历史最近一条非空 name（**保留原兜底**）→ `''`
  - 每道独立 try/except，失败降级到下一道，不中断
  - 依赖：T2.7
  - 验收：T5.4 4 道优先级测试通过；手动删 index_info 一行后重新抓取，name 仍能补上

**TDD 提示**：T5.1 / T5.4 测试必须**先于** T2.4-T2.6 / T2.8 写。先写 storage 期望接口，再实现。

---

### T3. 后端 Task 层

**Effort Estimate**: Small（2-3 小时）

#### Sub-tasks:

- [ ] **T3.1** `task/fetch_all_indexes_task.py` 骨架
  - `def fetch_all_indexes_task(force_run: bool = False) -> None`
  - 顶部注释：`# TODO: linked_fund_code / linked_field 字段后续加入 index_basic 后可数据驱动化；详见 PRD "index-basic-table" §5 非目标。`
  - 从 `IndexBasicStorage().list_enabled()` 读列表；空则 `logger.warning("无启用指数，跳过")` + return
  - 依赖：T2.3
  - 验收：`python -c "from app.task.fetch_all_indexes_task import fetch_all_indexes_task; print(fetch_all_indexes_task)"` 不报错

- [ ] **T3.2** ThreadPoolExecutor 循环 + 隔离
  - `with ThreadPoolExecutor(max_workers=4) as ex:`
  - 每支起一个 future：`future = ex.submit(fetch_and_store_index_with_market, code, market, force_run)`
  - 每个 future 包一层 `try/except Exception as e: logger.error(...); return None`（用 wrapper 函数）
  - `for future in as_completed(futures): result = future.result()` 收集 `Optional[KcIndexData]`
  - 依赖：T3.1
  - 验收：T5.3 `test_concurrent_fetch_uses_threadpool` / `test_single_failure_does_not_block_others` 通过

- [ ] **T3.3** kc100 副作用（保留硬编码 + TODO）
  - 在 `as_completed` 循环后**单线程**扫一遍 results
  - 找到 `r.index_code == '000698' and r` 时调 `FundInfoStorage().update_fund_remark('020292', f"{r.change_percent:.2f}")`
  - try/except `Exception as e: logger.error(f"更新 fund_info 020292 remark 失败: {e}")` 不中断
  - 依赖：T3.2
  - 验收：T5.3 `test_kc100_side_effect_runs_after_concurrent` / `test_kc100_side_effect_swallows_exception` 通过

- [ ] **T3.4** `task/register_task.py` +1 行
  - 在现有 `scheduler.register_task(...)` 调用附近新增 1 行：
    ```python
    scheduler.register_task('fetch_all_indexes_task', fetch_all_indexes_task)
    ```
  - 顶部 import：`from .fetch_all_indexes_task import fetch_all_indexes_task`
  - **不删** `INDEX_TASK_REGISTRY` 字典 + 4 个 wrapper 闭包（回滚通道）
  - 依赖：T3.3
  - 验收：`grep "fetch_all_indexes_task" data-crawler/app/task/register_task.py` 至少 2 行命中（import + register）

**TDD 提示**：T5.3 全部测试**先于** T3.2/T3.3 写。T3.1 骨架可与 T5.3 并行。

---

### T4. 后端 API 层

**Effort Estimate**: Small（3-4 小时）

#### Sub-tasks:

- [ ] **T4.1** `api_server.py` 顶部 storage 单例
  - 文件顶部（约 line 17-31）追加：
    ```python
    _index_basic_storage = IndexBasicStorage()
    ```
  - 顶部 import 加：`from app.storage import IndexBasicStorage`
  - 依赖：T2.7
  - 验收：`grep "_index_basic_storage" data-crawler/app/web/api_server.py` 至少 2 行命中

- [ ] **T4.2** `GET /api/index-basics` 列表
  - query params: `include_disabled`（默认 false）、`page`（默认 1）、`page_size`（默认 20）
  - 调 `_index_basic_storage.list_all(include_disabled=...)` + 分页（参照 `/api/funds` 或 `/api/buyers`）
  - 返 `{list: [...], total: N, page, page_size}`
  - 走 `@log_request`
  - 依赖：T4.1
  - 验收：T5.2 `test_list_endpoint_returns_enabled_by_default` 通过

- [ ] **T4.3** `GET /api/index-basics/<index_code>` 详情
  - 调 `_index_basic_storage.get(index_code)`，None 返 404
  - 依赖：T4.2
  - 验收：T5.2 `test_get_endpoint_returns_404_for_missing` 通过

- [ ] **T4.4** `POST /api/index-basics` 新增
  - body: `{index_code, market, index_name, index_type?, enabled?}`
  - 调 `_index_basic_storage.create(data)`
  - ValueError 返 400 + `{error: msg}`
  - 依赖：T4.3
  - 验收：T5.2 `test_create_endpoint_rejects_invalid_market` 通过

- [ ] **T4.5** `PUT /api/index-basics/<index_code>` 编辑
  - body 同上但 `index_code` 被白名单过滤
  - 调 `_index_basic_storage.update(index_code, data)`
  - 依赖：T4.4
  - 验收：T5.2 `test_update_endpoint_ignores_index_code_in_body` 通过

- [ ] **T4.6** `DELETE /api/index-basics/<index_code>` 软删
  - 调 `_index_basic_storage.soft_delete(index_code)`
  - 返 `{success: true}`
  - 依赖：T4.5
  - 验收：T5.2 `test_delete_endpoint_calls_soft_delete` 通过

- [ ] **T4.7** `POST /api/index-basics/<index_code>/toggle` 启停
  - body: `{enabled: 0|1}` 转 bool
  - 调 `_index_basic_storage.toggle_enabled(index_code, enabled)`
  - 依赖：T4.6
  - 验收：T5.2 `test_toggle_endpoint_updates_enabled` 通过

**TDD 提示**：T5.2 测试**先于** T4.2-T4.7 写。T4.1 单例可与 T5.2 并行。

---

### T5. 后端测试（TDD 先写）

**Effort Estimate**: Medium（4-6 小时）

#### Sub-tasks:

- [ ] **T5.1** `tests/test_index_basic_storage.py`
  - 用 sqlite in-memory 或 mock `IndexBasicStorage`（参照 `test_fund_buyer.py` 纯函数风格）
  - 8 个 case：`test_list_enabled_only_returns_enabled` / `test_list_include_disabled_returns_all` / `test_create_validates_market` / `test_create_validates_index_code_length` / `test_soft_delete_keeps_row` / `test_toggle_enabled_changes_flag` / `test_get_returns_none_for_missing` / `test_update_changes_name_only`
  - 依赖：无（先于 T2.4-T2.6 写）
  - 验收：`pytest tests/test_index_basic_storage.py -q` 全 8 个 case 通过

- [ ] **T5.2** `tests/test_index_basic_api.py`
  - 参照 `test_index_api.py` 风格，`api._index_basic_storage = MagicMock()` fixture
  - 6 个 case（覆盖 T4.2-T4.7）
  - 依赖：无（先于 T4 写）
  - 验收：`pytest tests/test_index_basic_api.py -q` 全 6 个 case 通过

- [ ] **T5.3** `tests/test_fetch_all_indexes_task.py`
  - `@patch('app.task.fetch_all_indexes_task.IndexBasicStorage')` + `@patch('app.task.fetch_all_indexes_task.FundInfoStorage')` + `@patch('app.task.fetch_all_indexes_task.fetch_and_store_index_with_market')`
  - 5 个 case：`test_no_enabled_indexes_logs_and_returns` / `test_concurrent_fetch_uses_threadpool` / `test_single_failure_does_not_block_others` / `test_kc100_side_effect_runs_after_concurrent` / `test_kc100_side_effect_swallows_exception`
  - 依赖：无（先于 T3.2/T3.3 写）
  - 验收：`pytest tests/test_fetch_all_indexes_task.py -q` 全 5 个 case 通过

- [ ] **T5.4** `tests/test_index_info_storage_name_fallback.py`
  - mock `IndexBasicStorage`、`KcIndexParser.INDEX_NAME_MAP`、历史查询
  - 5 个 case：每个 name 兜底层独立覆盖（`test_falls_back_to_index_basic` / `test_falls_back_to_parser_map` / `test_falls_back_to_history` / `test_uses_first_available` / `test_returns_empty_when_all_unavailable`）
  - 依赖：无（先于 T2.8 写）
  - 验收：`pytest tests/test_index_info_storage_name_fallback.py -q` 全 5 个 case 通过

**TDD 提示**：**T5 是 T2/T3/T4 实现的前置门禁**。每个 T5.x 写完 → 对应 T2/T3/T4 子任务才能开始。T5.x 自身先失败（red）→ 写实现 → 通过（green）。

---

### T6. 前端

**Effort Estimate**: Medium（6-8 小时）

#### Sub-tasks:

- [ ] **T6.1** `api/index.js` 新增 `indexBasicApi`
  - 位置：在 `indexApi` 块（line 263-273）之后插入
  - 6 方法：`list({ includeDisabled, page, pageSize })` / `get(code)` / `create(data)` / `update(code, data)` / `remove(code)` / `toggle(code, enabled)`
  - 路径前缀 `/index-basics`
  - 依赖：无
  - 验收：`grep "indexBasicApi" frontend/src/api/index.js` 至少 7 行命中（1 export + 6 method）

- [ ] **T6.2** `IndexBasic.vue` 骨架 + 搜索区
  - `defineOptions({ name: 'IndexBasic' })`
  - `import { ref, onMounted } from 'vue'`
  - `import { ElMessage, ElMessageBox } from 'element-plus'`
  - `import { indexBasicApi } from '@/api'`
  - 模板：外层 `el-card` 无边框无阴影 + 搜索区（参考 `FundManage.vue:5-24` + `Design §6.1`）
  - 依赖：T6.1
  - 验收：浏览器 `npm run dev` 打开 `/index-basic` 显示搜索区，搜索/重置调 API

- [ ] **T6.3** 功能区
  - 「+ 新增指数」按钮 + 「显示已停用」el-switch
  - 顶栏 div 用 `actions` 类（参考 `Design §6.2`）
  - `includeDisabled` ref 切到 true/false 时重 fetch 列表
  - 依赖：T6.2
  - 验收：切换「显示已停用」开关调 API 传 `includeDisabled` 参数

- [ ] **T6.4** 表格（含 el-switch 行内 + 市场 tag + 状态点）
  - 列：code / name / market / index_type / enabled / create_time / update_time / 操作
  - market 列用 el-tag：sh→primary 蓝、sz→warning 金
  - enabled 列用 6px 圆点 + 文字（参考 `Design §6.3`）
  - 操作列：el-switch + 编辑 link + 删除 link
  - 分页：el-pagination（参考 `IndexInfo.vue:103-110`）
  - 依赖：T6.3
  - 验收：表格渲染 4 行初始数据；el-switch 即时切换生效；市场 tag 颜色正确

- [ ] **T6.5** 新增/编辑 dialog
  - 弹窗 form：index_code（编辑时 disabled）/ market（编辑时 disabled）/ index_name / index_type / enabled
  - 校验规则（参考 `Design §6.4`）
  - `submit` 调 create/update API，成功关闭 dialog + 刷新 + ElMessage.success
  - 依赖：T6.4
  - 验收：新增 1 条 + 编辑 1 条均成功，列表自动刷新

- [ ] **T6.6** 删除确认
  - `ElMessageBox.confirm`（参考 `Design §7.3`）
  - 话术包含「历史保留」字样
  - 调 `indexBasicApi.remove(code)`，成功刷新
  - 依赖：T6.5
  - 验收：删除弹窗出现；确认后行消失；取消不操作

- [ ] **T6.7** 启停逻辑 + 失败回滚
  - `function toggleEnabled(row, v) { const prev = row.enabled; row.enabled = v; indexBasicApi.toggle(row.index_code, v).then(...).catch(() => { row.enabled = prev; ElMessage.error(...) }) }`
  - 成功 toast「已启用 / 已停用」
  - 依赖：T6.4
  - 验收：行内 el-switch 即时翻转；网络失败时回滚 + 错误 toast

- [ ] **T6.8** `router/index.js` 重排 sort + 新增路由
  - 在 `/index` 父路由 children 中：
    - `/index/info` sort 保持 46
    - 新增 `/index/basic` sort 47，指向 `IndexBasic.vue`
    - `/index/analysis` sort 47 → 48
  - 依赖：T6.1
  - 验收：`grep "sort: 4[678]" frontend/src/router/index.js` 命中 3 条；菜单顺序：信息 → 基础 → 分析

- [ ] **T6.9** `Layout.vue` 图标 + iconMap
  - 第 75 行 import 列表追加 `Files`
  - 第 116-134 行 iconMap 加 `'/index/basic': Files`
  - 依赖：T6.8
  - 验收：浏览器侧边菜单「指数基础」项有图标显示（不再是兜底 Folder）

- [ ] **T6.10** `IndexInfo.vue:64` `index_name` 列兜底
  - 把 `<el-table-column prop="index_name" label="指数名称" width="120" />`
  - 改为带 `<template #default="{ row }">{{ row.index_name || '—' }}</template>` 的形式
  - 依赖：无
  - 验收：8月5/6 空 name 行显示为「—」而非空白

**TDD 提示**：前端无 pytest，但**逻辑可单测**——T6.7 启停回滚逻辑可拆出纯函数 + vitest 单测（可选，本期不强求）。建议 T6.1-T6.10 顺序执行。

---

### T7. 全量验证 + 构建门禁

**Effort Estimate**: Small（1-2 小时）

#### Sub-tasks:

- [ ] **T7.1** 后端全量 pytest
  - `cd data-crawler && python3 -m pytest tests/ -q`
  - 预期：全量通过，无回归
  - 依赖：T1, T2, T3, T4, T5
  - 验收：0 failures，0 errors

- [ ] **T7.2** 前端构建
  - `cd frontend && npm run build`
  - 预期：成功；`dist/` 含 `assets/index-*.js` + `assets/index-*.css`
  - 依赖：T6
  - 验收：build 退出码 0；`ls dist/assets/` 看到新 hash 文件

- [ ] **T7.3** 手动触发 `fetch_all_indexes_task` 一次
  - 通过 `/api/task/run/fetch_all_indexes_task` 或 `POST /api/index-basics` 后台触发
  - 检查 system_log：4 支指数全 OK
  - 检查 index_info 表当天/次日新行 `index_name` 非空
  - 依赖：T1.3（task_schedule 新行已存在）, T3
  - 验收：4 行新 index_info 的 `index_name` 含中文名（不再空）

- [ ] **T7.4** SQL 校验 `task_schedule` 状态
  - `SELECT task_func, COUNT(*) AS rows, SUM(enabled) AS enabled_count FROM task_schedule WHERE task_func LIKE 'fetch_index_task_%' OR task_func='fetch_all_indexes_task' GROUP BY task_func;`
  - 预期：5 行（4 老 + 1 新），老 4 条 `enabled_count=0`、新 1 条 `enabled_count=1`
  - 依赖：T1.3, T7.3
  - 验收：查询结果与预期一致

- [ ] **T7.5**（可选）部署文档更新
  - `docs/deployment.md` 追加 index-basic-table 部署步骤（DBA 跑 SQL 顺序、scheduler 重启、smoke test、回滚命令）
  - 依赖：T7.4
  - 验收：文档含「部署步骤 / 验证 / 回滚」三节

---

## Notes

### 依赖关系总览

```
T1 (SQL) ──────────────────┐
                           │
T5 (测试) ─┬─→ T2 (Storage) ─┐
           │                 ├─→ T4 (API) ──┐
           ├─→ T3 (Task) ────┤               ├─→ T7 (验证)
           │                 │               │
           └─→ (T2.8 间接)   │               │
                             │               │
                    T6 (前端) ────────────────┘
```

### 关键风险与缓解（PRD §7 同步）

1. **ThreadPool + kc100 副作用竞争**：T3.3 显式「`as_completed` 收集后单线程触发副作用」。
2. **SQL 迁移顺序错**：T1.4 dry-run 强制；T7.4 部署后校验。
3. **`fetch_index_task_<code>` 命名**：T1.3 SQL 用 `LIKE 'fetch_index_task_%'`，不是字面。
4. **name 4 道兜底独立 try/except**：T2.8 + T5.4 显式覆盖。
5. **INDEX_TASK_REGISTRY 保留**：T3.4 显式「不删」。

### 范围外（PRD §5 非目标）

- linked_fund_code 字段（020292 仍硬编码 + TODO 注释）
- 改 name 级联 UPDATE 历史 index_info
- 导入/导出、权限/审计、K线分时、task_schedule.func_args 改造、IndexAnalysis.vue 改动

### TDD 节奏硬约束

| 测试任务 | 阻塞的实现任务 |
|----------|----------------|
| T5.1 | T2.4, T2.5, T2.6 |
| T5.2 | T4.2, T4.3, T4.4, T4.5, T4.6, T4.7 |
| T5.3 | T3.2, T3.3 |
| T5.4 | T2.8 |

每条规则：先写测试（red）→ 写实现（green）→ 跑通后勾选。

### Git 提交流水建议

按以下 4 个原子 commit 拆（每 commit 可独立回滚）：

1. `sql: 新增 index_basic 表 + 迁移老 4 条抓取任务为单条统一任务`（T1 + T1.4 验证）
2. `feat(storage): IndexBasicStorage + 4 道 name 兜底`（T2 + T5.1 + T5.4）
3. `feat(task): fetch_all_indexes_task + register_task`（T3 + T5.3）
4. `feat(api+frontend): index-basics CRUD API + IndexBasic.vue + 路由/图标/IndexInfo 兜底`（T4 + T5.2 + T6 + T7.1 + T7.2）

后端可独立部署（commit 1+2+3），前端 commit 4 需在合并后跑 `npm run build` 并提交 `dist/`。
