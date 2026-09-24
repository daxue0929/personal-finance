# PRD: 基金买入流水补录（buyer-backfill）

**Feature slug**: `buyer-backfill`

## 1. 概述

基金买入流水页（`FundBuyer.vue`）新增「补录」按钮：对以前忘记或缺失的买入流水，一步到位补录--创建买入记录 + 立即按买入日净值算份额 + 立即更新持仓（加权成本累加）。不用像现在"新增(PENDING)+刷新份额"两步、不等定时任务。

## 2. 功能目标

- 前端 `FundBuyer.vue` 加「补录」按钮 + 弹窗（基金、买入日期[可过去]、买入金额、类型、备注）。
- 后端新接口 `POST /api/buyers/backfill`：取 buy_date 历史净值 -> 算份额 -> 建买入记录 -> 原子累加持仓，一步返回结果。
- 份额 = 金额 / 买入日净值（复用 `get_nav_value_by_date` + 抽纯函数 `compute_buyer_shares`）。
- 净值缺失 -> 报错"请先录入该日净值"，不补录。
- 无持仓 -> 仍记录买入（SUCCESS）+ 提示"无该基金持仓，请先建持仓"，不更新持仓。
- 持仓更新异常 -> 买入保持 PENDING（任务稍后重试），返回错误。

## 3. 用户故事

- 作为用户，我想一键补录以前漏记的买入，立即看到份额算出、持仓更新，不用两步操作。
- 作为用户，补录时若该日净值没录，我想被明确提示去补净值，而不是静默 PENDING。
- 作为用户，补录的基金若还没建持仓，我想知道"买入已记但持仓没更新，先去建仓"。

## 4. 功能需求

1. **纯函数**（`fund_buyer_storage.py`）：`compute_buyer_shares(amt, nav) -> Decimal(4位)`，`nav<=0` 返回 None。`calculate_buyer_shares_task` 改用此函数（DRY）。
2. **后端接口**（`api_server.py`）：`POST /api/buyers/backfill`，body `{fund_code, fund_name, time, amt, type, remark}`。
   - 校验 fund_code/time/amt（amt>0）。
   - `nav = get_nav_value_by_date(_fund_info_storage, _nav_history_storage, fund_code, time)`；None/<=0 -> 400 `{error: "无法获取 {time} 的净值，请先录入该日净值"}`。
   - `shares = compute_buyer_shares(amt, nav)`。
   - 建买入记录（PENDING，复用 create_buyer 路由的内联建法拿 id）。
   - `process_buyer_transaction([id], fund_code, shares, amt, nav, time)` -> SUCCESS/NO_POSITION/ERROR。
   - SUCCESS -> `{success, shares, position_updated:true, message:"补录成功，持仓已更新"}`。
   - NO_POSITION -> `{success, shares, position_updated:false, message:"补录成功，但该基金无持仓，未更新持仓（请先建持仓）"}`。
   - ERROR -> 500 `{error:"补录失败（持仓更新异常），买入记录保持待处理，将稍后重试"}`。
3. **前端 API**（`api/index.js`）：`buyerApi.backfill(data)`。
4. **前端**（`FundBuyer.vue`）：功能栏加「补录」按钮 -> 弹窗（FundSelect 选基金、买入日期默认今天可改过去、买入金额、类型默认手工、备注）。提交调 `backfill`，按 `position_updated` 显示不同提示，刷新列表。

## 5. 验收标准

- [ ] `compute_buyer_shares(1000, 1.5)` == 666.6667；`nav<=0` 返回 None。
- [ ] 补录：填过去日期+金额 -> 后端取该日净值算份额 -> 建记录 + 更新持仓 -> 返回 shares + position_updated:true。
- [ ] 该日净值缺失 -> 400 提示"请先录入该日净值"，不建记录。
- [ ] 无持仓 -> 建记录(SUCCESS) + position_updated:false + 提示"请先建持仓"。
- [ ] 持仓更新异常 -> 买入保持 PENDING + 500 提示。
- [ ] 前端补录弹窗提交后按 position_updated 显示提示、刷新列表。
- [ ] `compute_buyer_shares` 单测（TDD）；`calculate_buyer_shares_task` 改用后 `pytest tests/ -q` 无回归。
- [ ] `npm run build` 通过，`dist/` 提交。

## 6. 非目标

- 不做补录卖出版（仅买入）。
- 不做历史快照回填（补录只影响未来快照，已确认）。
- 不做按日期去重（用户自行避免重复补录）。
- 不改 `process_buyer_transaction` / `get_nav_value_by_date` 既有逻辑。
- 不改"新增买入"和"刷新份额"既有流程。

## 7. 依赖

- `get_nav_value_by_date`（nav_utils，已存在）。
- `process_buyer_transaction`（fund_buyer_storage，已存在，原子累加持仓）。
- `FundSelect` 组件（选基金，已存在）。
- `_fund_info_storage` / `_nav_history_storage`（api_server 需实例化或路由内建）。

## 8. 风险评估

- **净值缺失**：历史日期无净值 -> 报错提示，用户先补净值。明确不静默。
- **重复补录**：同一笔买入补录两次会双倍累加。无去重，用户负责（非目标）。
- **非原子**：建记录(commit) 与 process(另一 session) 分两步；process 失败则记录留 PENDING，任务重试。可接受（与现有 task 一致）。
- **过去日期**：`process_buyer_transaction` 已支持补录历史/同日买入（不依赖 buy_date 水位）。

## 9. Open Questions（Phase 3 已澄清）

- **补录行为**：一步到位（创建+立即算份额+立即更新持仓）。
- **净值来源**：自动取 buy_date 历史净值（`get_nav_value_by_date`），缺失报错。
- **无持仓**：记录买入(SUCCESS) + 提示"请先建持仓"，不更新持仓。
- **feature slug**：`buyer-backfill`。
