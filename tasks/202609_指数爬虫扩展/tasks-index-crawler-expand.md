# Task List: index-crawler-expand

**Based on PRD**: `tasks/prd-index-crawler-expand.md`
**Design**: backend-only，无前端设计文档（指数页动态读取，无需改前端）
**状态**: ✅ 全部完成（实跑验证 000300/399673 入库，scheduler 已注册新任务）

## Relevant Files

### Files to Create
- `data-crawler/app/task/index_fetch_helper.py` - 指数抓取公共逻辑（is_trading_time + fetch_and_store_index）✅
- `data-crawler/app/task/fetch_hs300_index_task.py` - 沪深300(000300) 任务 ✅
- `data-crawler/app/task/fetch_cyb50_index_task.py` - 创业板50(399673) 任务 ✅
- `data-crawler/tests/test_index_crawler_expand.py` - parser + helper 测试（9 例）✅
- `sql/alter/seed_hs300_cyb50_index_task.sql` - task_schedule 2 行 cron 配置 ✅

### Files to Modify
- `data-crawler/app/parser/kc_index_parser.py` - INDEX_CONFIG 加 market + 2 指数；URL 改 {market}{index_code} ✅
- `data-crawler/app/task/fetch_kc50_index_task.py` - 重构为调 helper ✅
- `data-crawler/app/task/fetch_kc100_index_task.py` - 重构为调 helper，保留 fund 020292 remark 副作用 ✅
- `data-crawler/app/task/register_task.py` - 注册 2 个新任务 ✅

### 不改动
- 前端（IndexInfo/IndexAnalysis 动态读 `getOptions`，现返回 4 个指数）
- `index_info` 表结构
- scheduler cron 检查/热加载机制

## Implementation Tasks

### 1. Parser 扩展（TDD）✅
- [x] 1.1 **[测试先行]** 新建 `tests/test_index_crawler_expand.py`，parser 用例：INDEX_CONFIG 含 000300(sh)/399673(sz)；URL 含 sh000300/sz399673；现有 000688 仍 sh；不支持代码 raise ValueError
- [x] 1.2 跑测试确认失败（红）-- 4 failed（ValueError/AttributeError/KeyError）
- [x] 1.3 `kc_index_parser.py`：INDEX_CONFIG 加 market + 2 指数；TENCENT_URL 改 `{market}{index_code}`；`__init__` 设 `self.market`；fetch 用 market；更新 docstring
- [x] 1.4 跑 parser 用例通过（绿）-- 5 passed

### 2. Helper 抽取（TDD）✅
- [x] 2.1 **[测试先行]** helper 用例（mock parser/storage）：force_run 入库 dict 含 index_type/source/返回 KcIndexData；非交易时段跳过；fetch None 不入库
- [x] 2.2 跑测试确认失败（红）-- module not found
- [x] 2.3 新建 `app/task/index_fetch_helper.py`：`is_trading_time()` + `fetch_and_store_index(index_code, force_run)`
- [x] 2.4 跑 helper 用例通过（绿）

### 3. 重构 kc50/kc100 复用 helper ✅
- [x] 3.1 `fetch_kc50_index_task.py` 改为调 `fetch_and_store_index('000688', force_run)`
- [x] 3.2 `fetch_kc100_index_task.py` 改为调 helper，保留 fund 020292 remark 副作用
- [x] 3.3 跑 `pytest tests/ -q` 确认无回归 -- 顺手修复 `storage.close()` 潜在 bug（IndexInfoStorage 无 close，原靠 run_with_trace_context 兜底）

### 4. 新增 2 任务 + 注册 ✅
- [x] 4.1 新建 `fetch_hs300_index_task.py`（调 helper '000300'）
- [x] 4.2 新建 `fetch_cyb50_index_task.py`（调 helper '399673'）
- [x] 4.3 `register_task.py` 加 import + register 2 个新任务

### 5. task_schedule 配置 ✅
- [x] 5.1 查 `task_schedule` 现有 kc50/kc100 行格式（id=2/4，cron `* 9-15 * * mon-fri`）
- [x] 5.2 新建 `sql/alter/seed_hs300_cyb50_index_task.sql`（2 行 cron）
- [x] 5.3 执行 seed（MCP，2 行插入）+ 重启 scheduler，日志确认「沪深300/创业板50指数抓取任务 已注册」+ cron 已设置

### 6. 实跑验证 + 质量收尾 ✅
- [x] 6.1 `force_run=True` 实跑 2 个新任务，确认 000300/399673 入库 `index_info`（2026-07-25，source=腾讯财经，PE 有值）
- [x] 6.2 `pytest tests/ -q` 全量回归 -- 205 passed + 9 新测试；12 failed+2 error 均为预存在（eastmoney 搁置模块、fund_homepage_fetch 网络测试），无回归
- [x] 6.3 对照 PRD 验收标准逐条核对 -- 全部达标
- [x] 6.4 reviewer 自审（简洁/DRY、功能正确性、项目规范）-- 通过；helper 消除 4 任务重复，close() bug 修复
- [x] 6.5 总结见下

## Notes

- **用户已批准重构现有 kc 任务**（B+），符合 overlay"除非明确要求重构"豁免。
- **顺手修复 close() 潜在 bug**：原 kc50/kc100 的 `storage.close()`/`fund_storage.close()` 调用了不存在的方法（StorageBase 无 close），靠 scheduler 的 run_with_trace_context 兜底吞异常（数据已存但 finally 报错）。session-per-method 模式下 storage 无需 close，重构时移除，4 个指数任务全部受益。
- **scheduler 已重启**（本会话）：新进程注册了 2 个新任务函数 + 热加载 2 行 task_schedule cron。web 进程未重启（转发 localhost:5002 不变）。
- **类名 `KcIndexParser` 保留**（docstring 说明已扩展）。
- **存量 000300 历史 4999 条**（东方财富抓的）不受影响；Tencent 仅更新今日记录。
