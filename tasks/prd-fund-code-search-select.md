# PRD：基金代码下拉搜索选择框（公共组件 + 全站统一）

## 1. 概述

将前端各界面中「需要输入/选择基金代码」的控件，统一重构为一个可复用的下拉搜索选择组件 `FundSelect`。组件支持下拉直接选择、输入关键字动态模糊搜索（基金代码-基金名称形式）、聚焦时预载默认列表。用该组件替换现有分散且重复的 9 处实现，消除 5 份几乎逐字相同的样板代码。

后端无需改动：`/api/funds?keyword=` 已支持 `fund_code` / `fund_name` 的 OR 模糊匹配，空 `keyword` 返回首页前 N 条。

## 2. 目标

- **统一交互**：全站基金选择体验一致--下拉可选 + 动态搜索 + 模糊匹配（代码或名称）。
- **消除重复**：用一个公共组件替代 9 处分散实现，后续维护只改一处。
- **真·服务端搜索**：把 4 处「假远程」（拉全量 1000 条本地过滤）统一改为后端 `keyword` 搜索，避免基金增多后的首屏慢与内存占用。
- **可测试**：引入 vitest，组件行为先有测试再实现（TDD）。

## 3. 用户故事

- 作为录入人员，我在买入/卖出/持仓等表单里选择基金时，希望直接下拉看到常用基金，也能输入代码或名称片段快速搜索，而不必记住完整代码。
- 作为列表查询者，我在买入/卖出/持仓列表的搜索栏里，希望像选择一样挑出某只基金来过滤列表，而不是手敲代码。
- 作为维护者，我希望基金选择逻辑只在一处实现，改一处即全站生效。

## 4. 功能需求

1. 新建公共组件 `frontend/src/components/FundSelect.vue`（`<script setup>` + scoped，与项目约定一致）。
2. 组件行为：
   - 选项 label 统一 `` `${fund_code} - ${fund_name}` ``，value 为 `fund_code`。
   - 聚焦且未输入关键字时，显示前 20 条基金（后端 `getFunds({page:1, page_size:20})`，空 keyword）。
   - 输入关键字时，调 `getFunds({keyword, page:1, page_size:20})` 做代码/名称 OR 模糊搜索；带 loading 态。
   - 输入搜索做防抖（约 300ms），避免逐键打后端。
   - 支持 `clearable`、`reserve-keyword`、`filterable`、`remote`（el-select 远程模式）。
3. 组件接口：
   - `v-model`（fund_code，string）。
   - `@select(fund)`：选中时抛出整个 fund 对象，供需要联动回填（基金名称、净值）的页面使用。
   - props：`placeholder`、`width`、`disabled`、`clearable`、`pageSize`（默认 20）。
   - 初始值回显：当 `v-model` 预设了 fund_code（如路由参数带入）但选项列表尚无对应项时，组件按该 code 解析并回显 "code - name" label。
4. 替换 9 处（见 §6 改动文件）。`FundManage`「新增基金」弹窗的代码输入框**不在范围**，保持纯文本。
5. 各页面原有联动逻辑保留：
   - PositionManage：选中后带出 fund_name 与 net_asset_value 作为 current_price。
   - PortfolioBoard：选中后查已有持仓并提示「将直接关联」。
   - FundBuyer/FundSeller：选中后回填 fund_name（若现有有此联动）。
   - FundNavHistory：支持 `route.query.fund_code` 预填并回显。
   - 各列表搜索栏：选中后作为过滤条件触发查询。
6. 编辑态锁定：PositionManage、FundBuyer 编辑等原有 `:disabled="isEdit"` 行为保留，经组件 `disabled` prop 透传。

## 5. 非目标（Out of Scope）

- 不改造 `FundManage`「新增基金」弹窗的基金代码输入框（创建新基金，需手输新代码）。
- 不新增后端接口、不改后端逻辑（复用现有 `/api/funds`）。
- 不做「最近使用」「收藏」等个性化默认列表（首期用前 20 条）。
- 不引入 Pinia/Vuex 做全局状态（组件内自管理）。
- 不处理指数代码选择（IndexAnalysis 用 indexCode，非基金代码）。

## 6. 依赖与改动文件

**新增**：
- `frontend/src/components/FundSelect.vue`
- `frontend/src/components/FundSelect.spec.js`（vitest 组件测试）
- `frontend/vitest.config.js` 或在 `vite.config.js` 增加 test 配置
- `package.json` 增加 `vitest`、`@vue/test-utils`、`jsdom`（倒数第二稳定版）

**改动（9 处替换，跨 6 文件）**：
1. `frontend/src/views/FundManage.vue` -- 搜索栏 el-select（第 8-20 行）→ FundSelect
2. `frontend/src/views/FundBuyer.vue` -- 新增/编辑买入 el-select（第 140 行）→ FundSelect
3. `frontend/src/views/FundBuyer.vue` -- 快捷买入 el-select（第 190 行）→ FundSelect
4. `frontend/src/views/FundBuyer.vue` -- 搜索栏 el-input（第 8 行）→ FundSelect
5. `frontend/src/views/FundSeller.vue` -- 新增/编辑卖出 el-select（第 153 行）→ FundSelect
6. `frontend/src/views/FundSeller.vue` -- 搜索栏 el-input（第 8 行）→ FundSelect
7. `frontend/src/views/PortfolioBoard.vue` -- 添加持仓 el-select（第 145-154 行）→ FundSelect
8. `frontend/src/views/PositionManage.vue` -- 新增/编辑持仓 el-select（第 83-93 行）→ FundSelect
9. `frontend/src/views/FundNavHistory.vue` -- 全量 el-select（第 8-21 行）→ FundSelect

**后端**：无改动。**API 层**：无改动（复用 `fundApi.getFunds`）。

## 7. 验收标准

- 9 处全部改用 `FundSelect`，删除各文件内重复的 `searchFunds`/`fundOptions`/`searchQuickBuyFunds` 等本地实现。
- 任意一处：点开下拉显示前 20 条；输入代码或名称片段能模糊搜索并带 loading；选中后 value 为 fund_code、label 为 "code - name"。
- PositionManage/PortfolioBoard 选中基金的联动回填行为与改造前一致。
- FundNavHistory 从 FundManage 点「历史」跳转带 `fund_code` 时，下拉正确回显该基金。
- 编辑态下对应选择框被禁用（与原行为一致）。
- vitest 测试先于实现编写并通过：覆盖默认加载、搜索、防抖、选中抛出、初始值回显等行为。
- `npm run build` 通过，`dist/` 更新并随源码提交。
- 无控制台报错；原有功能（增删改查、分页、搜索）回归正常。

## 8. 风险

- **回归面广**：9 处替换跨 6 文件，漏改或联动丢失风险。缓解：逐文件对照原行为，质量审查阶段逐处核对。
- **行为变化**：4 处由本地全量过滤改为后端逐键搜索，首键有网络延迟。缓解：300ms 防抖 + loading 态。
- **新增测试依赖**：vitest 与现有 vite 5 / vue 3.4 版本兼容性。缓解：选倒数第二稳定版，安装后先跑空测试验证配置。
- **初始值回显**：路由预填 fund_code 时需异步解析 label，期间下拉显示空 label 可能闪动。缓解：组件挂载即解析。

## 9. Open Questions（澄清结果回写）

- ✅ 范围：全部统一（5 已有 + 3 搜索栏 + 净值历史页）。
- ✅ 新增基金弹窗：保持纯文本，不改造。
- ✅ 默认下拉：前 20 条（后端空 keyword 首页）。
- ✅ TDD：引入 vitest + @vue/test-utils，先写测试再实现。
- ⏳ 组件接口细节（props/emits 最终签名、防抖时长、初始值回显策略）在架构设计阶段确定。
- ⏳ vitest 具体版本与配置（独立 vitest.config 还是并入 vite.config）在实现阶段确定。

## 10. 后续可能的演进

- 「最近使用/收藏」基金作为默认下拉内容。
- 基金代码格式校验（6 位等）。
- 把同样的下拉搜索模式抽到指数代码选择。
