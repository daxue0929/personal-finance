# PRD: 指数爬虫扩展（index-crawler-expand）

**Feature slug**: `index-crawler-expand`

## 1. 概述

指数爬虫（`KcIndexParser` + 各指数 task）当前硬编码仅支持科创50(000688)、科创100(000698)，且 `TENCENT_URL` 固定 `sh` 前缀，无法抓深圳指数。本功能扩展支持沪深300(000300, sh) 与创业板50(399673, sz)，并抽取公共抓取逻辑消除 kc50/kc100 间的重复（用户已批准重构现有任务）。

## 2. 功能目标

- `INDEX_CONFIG` 新增 000300(sh)、399673(sz)，并加 `market`(sh/sz) 字段。
- `TENCENT_URL` 改为 `{market}{index_code}`，支持 sh/sz 前缀。
- 抽取公共 helper `fetch_and_store_index`，重构 kc50/kc100 复用，新增沪深300/创业板50 任务。
- 注册 2 个新任务，`task_schedule` 配 cron `* 9-15 * * mon-fri`。
- 指数信息页/分析页自动展示新指数（前端动态读取，无需改）。

## 3. 用户故事

- 作为用户，我想在指数信息页看到沪深300、创业板50 的行情。
- 作为用户，我想在指数分析页对这两个指数做分析。

## 4. 功能需求

1. **Parser**（`kc_index_parser.py`）：`INDEX_CONFIG` 加 `market` 字段 + 2 指数；`TENCENT_URL` 改 `{market}{index_code}`；`__init__` 设 `self.market`；`fetch()` 用 market 拼 URL；更新 docstring。
2. **Helper**（新建 `app/task/index_fetch_helper.py`）：含 `is_trading_time()` + `fetch_and_store_index(index_code, force_run)`，负责交易时段判断 + 拉取 + 入库 `index_info`，返回 `KcIndexData | None`。
3. **重构** `fetch_kc50_index_task` / `fetch_kc100_index_task` 调 helper；kc100 保留更新 fund 020292 remark 的副作用。
4. **新任务**：`fetch_hs300_index_task`(000300) / `fetch_cyb50_index_task`(399673)，薄封装调 helper。
5. **注册**：`register_task.py` 注册 2 个新任务。
6. **调度配置**：`task_schedule` 加 2 行 cron `* 9-15 * * mon-fri`（seed SQL + 执行）。
7. **数据约定**：`index_type='宽基指数'`、`source='腾讯财经'`（与现有一致）。

## 5. 验收标准

- [ ] `KcIndexParser('000300')` market=sh、URL=`sh000300`；`KcIndexParser('399673')` market=sz、URL=`sz399673`。
- [ ] 不支持的指数代码仍 raise `ValueError`。
- [ ] helper `fetch_and_store_index` 成功调 `IndexInfoStorage.create_or_update_index_info`，dict 含 `index_type='宽基指数'`、`source='腾讯财经'`；非交易时段（非 force_run）跳过；返回 `KcIndexData`。
- [ ] kc50/kc100 重构后行为不变（kc100 仍更新 020292 remark）。
- [ ] 2 个新任务注册成功，scheduler 热加载后日志可见。
- [ ] 实跑 `force_run=True` 成功入库 000300/399673（验证接口真实可用）。
- [ ] `pytest tests/ -q` 无回归。
- [ ] 前端无需改（指数页动态读取 `getOptions`）。

## 6. 非目标

- 不做 PE分位/换手率（腾讯接口无，与现有一致；PE 有值、PB=0 由解析器守卫处理）。
- 不改 `index_info` 表结构。
- 不改前端。
- 不重命名 `KcIndexParser` 类（最小改动；docstring 说明已扩展支持沪深300/创业板50）。
- 不动 scheduler cron 检查/热加载机制。
- 不处理存量 000300 历史 4999 条（东方财富抓的）；Tencent 仅更新今日记录（create_or_update by code+date）。

## 7. 依赖

- 腾讯 `qt.gtimg.cn` 接口（已验证 000300/399673 返回 88 段、格式与 000688 一致）。
- `IndexInfoStorage.create_or_update_index_info`（已存在）。
- `task_schedule` 热加载机制（60s hash 比对）。

## 8. 风险评估

- **399673 接口格式**：已验证一致（88 段，PE=38.69 有值）。低风险。
- **重构 kc50/kc100 引入回归**：靠 TDD（helper 单测）+ 实跑 force_run 验证。
- **task_schedule 行未插入则任务不调度**：seed SQL + 执行 + 看 scheduler 日志确认 2 任务注册。
- **类名 KcIndexParser 名不副实**：docstring 已说明；不重命名避免连带改动。

## 9. Open Questions（Phase 3 已澄清）

- 任务结构：用户选 **B+**（helper + 重构现有 kc 任务）。
- 类名保留 `KcIndexParser`。
- `index_type='宽基指数'`、`source='腾讯财经'`。
- 现有 000300 历史数据不受影响（仅更新今日）。
