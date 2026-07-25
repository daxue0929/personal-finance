# Task List: tags-view

**Based on PRD**: `tasks/prd-tags-view.md`
**Design**: `tasks/design-tags-view.md`

## Relevant Files

### Files to Create
- `frontend/src/composables/useTagsView.js` - tab 状态 + 逻辑（addTab/closeTab/closeOthers/closeAll + affix 首页）
- `frontend/src/composables/useTagsView.spec.js` - composable 单测（vitest，TDD）
- `frontend/src/components/TagsView.vue` - 标签栏视图

### Files to Modify
- `frontend/src/components/Layout.vue` - el-header 与 el-main 之间插入 TagsView

### 不改动
- 后端、SQL、路由表（`router/index.js`）、侧边栏菜单结构

## Implementation Tasks

### 1. useTagsView composable（TDD）
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 1.1 **[测试先行]** 新建 `src/composables/useTagsView.spec.js`，9 用例：初始首页 affix / addTab 新路由+1 / 重复不增 / 跳过父路由 / closeTab 非活跃不跳 / closeTab 活跃右优先跳 / closeOthers / closeAll / affix 不可关
- [x] 1.2 跑 `npm run test` 确认失败（红）-- import 失败
- [x] 1.3 新建 `src/composables/useTagsView.js`：tabs ref + addTab(去重/跳过父路由) + closeTab(返回跳转 path) + closeOthers/closeAll + 初始化首页 affix
- [x] 1.4 跑 `npm run test` 通过（绿）-- 9 passed

### 2. TagsView.vue 视图
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 2.1 新建 `src/components/TagsView.vue`：渲染 tabs（激活态 EP 主色 #409EFF + 浅蓝底，非激活灰边，× 仅 hover/active 显示，affix 无 ×）；栏高 40px 白底底边框
- [x] 2.2 watch route.path -> `addTab`（仅叶子路由）；点 tab -> `router.push(path)`
- [x] 2.3 × 关闭：`closeTab` + 若关的是活跃 tab 则 `router.push(建议path)`
- [x] 2.4 右键上下文菜单：关闭当前/其他/全部（affix 不被关），定位 `clientX/clientY`，点击他处/滚动关闭
- [x] 2.5 tab 溢出 `overflow-x: auto` 横向滚动

### 3. Layout 集成
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 3.1 `Layout.vue`：el-header 与 el-main 之间插入 `<TagsView />`
- [x] 3.2 import TagsView

### 4. 构建门禁 + 质量收尾
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 4.1 `npm run test`（vitest）通过 -- 3 文件 29 测试全绿
- [x] 4.2 `npm run build` 通过 -- ✓ built in 3.24s
- [x] 4.3 `dist/` 纳入提交（构建门禁）-- 待 git 提交
- [x] 4.4 对照 PRD 验收标准 + design 一致性清单 -- 全部达标
- [x] 4.5 reviewer 自审 -- 通过（composable 可测、视图薄、复用 EP 默认）
- [x] 4.6 总结见下

## Notes

- **依赖顺序**：1（composable TDD）-> 2（视图）-> 3（集成）-> 4（构建+审查）。
- **纯前端**：无后端、无 SQL、无 pytest；前端测试用 vitest（复用 `frontend/vitest.config.js`），构建门禁 `npm run build`。
- **composable 放 `src/composables/`**（与 useEChart 一致），spec 同目录。
- **叶子路由判定**：`route.matched` 末位记录有 `components.default` 才是叶子（父菜单 isParent 无组件，不成 tab）。
- **首页 affix**：`/portfolio`（持仓看板）初始化入 tabs，`affix: true`，不可关闭。
- **刷新不持久化**：刷新重置为仅首页（本期非目标，后续可加 localStorage）。
