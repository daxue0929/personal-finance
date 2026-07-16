# 前端设计规范：FundSelect 基金代码下拉搜索选择组件

> 本规范作为 Phase 6 质量审查的对照基线。本组件是「统一替换」性质，设计目标是**与既有 Element Plus 界面一致**，不引入新视觉风格。

## 1. 设计目标与原则

- **一致性优先**：FundSelect 在视觉与交互上必须与现有 5 处 `el-select`（FundManage 搜索栏等）无感融合，不突出、不另类。
- **固化交互**：`filterable` / `remote` / `reserve-keyword` / `clearable` / 防抖 300ms / 默认 20 条，全部在组件内部固化，**不对外暴露为 prop**，防止 9 处调用方演化出变体（这正是当前 5 份重复实现的根源）。
- **遵循项目约定**：`<script setup>` + `<style scoped>`，放 `frontend/src/components/`，各 view 局部 import（不全局注册，与 Layout.vue 一致）。

## 2. 色彩规范

- **沿用 Element Plus 默认主题**，不新增色板、不改主题色。
- 继承 `Layout.vue` 中已有的 Element Plus CSS 变量覆盖（如 `--el-button-text-color`），不自定义新变量。
- 选中项高亮、loading 图标、clearable 清除按钮颜色均为 EP 默认（主色 `#409EFF` 系），与现有 el-select 一致。
- **不引入**渐变、阴影装饰、自定义背景色。

## 3. 字体规范

- 沿用项目既有字体（Element Plus 默认字体栈），不引入新字体。
- 选项 label、placeholder 字号与现有 el-select 一致（EP 默认 14px），不单独设字号。
- **label 格式统一**：`` `${fund_code} - ${fund_name}` ``（代码在前，连字符分隔）。注意 FundNavHistory 原为 `"name (code)"`，统一为本格式（预期内的小变更）。

## 4. 组件规范（FundSelect）

### 4.1 Props

| prop | 类型 | 默认 | 说明 |
|---|---|---|---|
| `modelValue` | String | `''` | v-model，fund_code |
| `placeholder` | String | `'输入代码或名称搜索'` | 录入场景；搜索栏可传 `'请选择基金'` |
| `width` | String | `'100%'` | 透传 el-select style；搜索栏传 `'160px'`~`'280px'` |
| `disabled` | Boolean | `false` | 编辑态锁定透传 |
| `clearable` | Boolean | `true` | |
| `pageSize` | Number | `20` | 每次拉取条数 |

**不暴露**（内部固化）：`filterable`、`remote`、`reserve-keyword`、防抖时长。

### 4.2 Emits

| event | payload | 说明 |
|---|---|---|
| `update:modelValue` | string | v-model 同步 fund_code |
| `select` | fund 对象 \| null | 选中抛完整 fund（含 fund_name/net_asset_value）；清空抛 null |

### 4.3 状态与交互

- **聚焦预载**：下拉展开（`visible-change(true)`）且当前无选项时，拉首页前 `pageSize` 条（后端空 keyword）。
- **动态搜索**：输入关键字经 300ms 防抖后调 `getFunds({keyword, page:1, page_size})`，带 loading 图标。
- **竞态保护**：composable 内 `_reqId` 递增，慢请求返回时若已过期则丢弃，避免快速输入闪烁错结果。
- **初始值回显**：`modelValue` 预设（路由参数 / 编辑态）但选项无对应项时，按 code 解析并回显 label，通过 `initialOption` 单独兜底，避免被后续搜索结果冲掉。
- **空状态**：搜索无结果时显示 Element Plus 默认空文案，不自定义。
- **disabled 态**：编辑模式下选择框置灰锁定，与原 `:disabled="isEdit"` 行为一致。

### 4.4 尺寸与布局

- 默认 `width: 100%`，跟随父容器（表单 `el-form-item` 内自适应）。
- 搜索栏场景显式传固定宽度（160px~280px），与原搜索栏控件宽度对齐。
- 高度沿用 EP 默认，不强制设定。

## 5. 结构（清洁架构 - composable 分离）

```
FundSelect.vue          组件层（薄壳）：props 接收 / el-select 绑定 / 事件转发 / initialOption 合并去重
  └─ useFundSearch.js   逻辑层（composable）：search(防抖) / loadDefault / resolveInitial / 竞态保护 / findInOptions
       └─ fundApi.getFunds（复用，不改）
```

- 逻辑层可独立单测（node 环境，注入 fetcher），组件层薄测（jsdom，mock `@/api`）。
- 依赖方向单向，逻辑层不 import 组件层。

## 6. 测试规范（TDD）

- 配置：独立 `frontend/vitest.config.js`（零改 vite.config.js），`environment: jsdom`，`include: src/**/*.{spec,test}.js`。
- 依赖：`vitest@2.1.9`、`@vue/test-utils@2.4.10`、`jsdom@25.0.1`（实现期 `npm view` 确认补丁号后 pin）。
- **先写测试再实现**：
  - `useFundSearch.spec.js`（逻辑层，约 12 例）：默认加载参数、防抖、空 query 分流、竞态丢弃、初始值命中/未命中、异常吞掉、findInOptions 去重、clear、pageSize 透传、loading 时序、fetcher 注入。
  - `FundSelect.spec.js`（组件层，约 6 例）：初始值回显触发、change 抛 code+fund、clear 抛 null、visible-change 预载去重、disabled 透传、mergedOptions 去重。
- 组件测试用 `vi.mock('@/api')`，通过 `findComponent(ElSelect)` 触发事件，绕开 jsdom 下 popper/teleport 的 DOM 脆性。

## 7. 一致性检查清单（Phase 6 对照）

- [ ] 9 处全部用 FundSelect，无残留 `searchFunds`/`fundOptions`/`funds` 本地过滤样板
- [ ] label 格式统一 `code - name`
- [ ] filterable/remote/reserve-keyword 未对外暴露，组件内固化
- [ ] 色彩/字体沿用 EP 默认，无新色板/新字体/装饰
- [ ] 各页联动回填经 `@select(fund)`，不依赖本地全量 `funds` 数组
- [ ] 编辑态 disabled 行为保留
- [ ] FundNavHistory 路由预填回显正常
- [ ] vitest 测试先于实现并通过
- [ ] `npm run build` 通过，`dist/` 提交
