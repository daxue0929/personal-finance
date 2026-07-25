# PRD: 前端多标签页 TagsView（tags-view）

**Feature slug**: `tags-view`

## 1. 概述

前端 Layout 新增多标签页（TagsView）：顶栏下方加一行 tab，访问过的页面成 tab，点击切换、可关闭。首页（持仓看板）固定不可关。右键菜单支持关闭当前/其他/全部。纯前端，无后端改动。

## 2. 功能目标

- 新增 `TagsView.vue` 组件 + `useTagsView` composable，集成到 Layout（el-header 与 el-main 之间）。
- 路由变化时自动新增 tab（去重），tab 显示页面标题（route.meta.title）。
- 点击 tab 切换路由；当前路由 tab 高亮。
- 关闭：tab 上的 × 关闭单个（固定 tab 除外）；右键菜单关闭当前/其他/全部。
- 首页 tab（/portfolio 持仓看板）固定（affix），始终在、不可关闭。
- 登录页不参与（不在 Layout 内）。

## 3. 用户故事

- 作为用户，我想在顶栏看到已打开的页面 tab，快速切换而不必反复点侧边栏。
- 作为用户，我想关闭不再需要的 tab，保持工作区整洁。
- 作为用户，首页 tab 始终在，方便回到看板。

## 4. 功能需求

1. 新建 `composables/useTagsView.js`：tab 状态 + 逻辑（addTab 去重、closeTab、closeOthers、closeAll、affixed 首页）。纯逻辑，可单测。
2. 新建 `components/TagsView.vue`：横向 tab 栏，渲染 tabs，点击切换、× 关闭、右键菜单。
3. 路由监听：watch route，对「有 meta.title 且有组件的叶子路由」新增 tab（去重）；父菜单路由（isParent 无组件）不成 tab。
4. 首页固定：初始化含 /portfolio（持仓看板）tab，标记 affix，不可关闭。
5. 点击 tab：`router.push(path)`。
6. 关闭单个：tab 上 ×（affix 除外）；关闭当前活跃 tab 后跳到相邻 tab（右侧优先，无则左侧，无则首页）。
7. 右键菜单：关闭当前 / 关闭其他 / 关闭全部（保留 affix）。
8. 集成 `Layout.vue`：el-header 与 el-main 之间插入 TagsView。

## 5. 验收标准

- [ ] 访问任意页面，顶栏出现对应 tab；重复访问不新增。
- [ ] 点 tab 切换到该页面；当前页 tab 高亮。
- [ ] tab 上 × 可关闭非固定 tab；关闭当前活跃 tab 后正确跳转相邻/首页。
- [ ] 右键 tab 弹菜单：关闭当前/其他/全部；固定 tab 不被关。
- [ ] 首页 tab（持仓看板）始终在、不可关。
- [ ] 登录页不显示 TagsView（不在 Layout）。
- [ ] `useTagsView.spec.js`（vitest）覆盖 addTab 去重 / closeTab / closeOthers / closeAll / affix。
- [ ] `npm run build` 通过，`dist/` 提交。

## 6. 非目标

- 不做 tab 刷新按钮（未确认，后续可加）。
- 不做 tab 拖拽排序。
- 不做 localStorage 持久化（刷新重置为仅首页，后续可加）。
- 不改侧边栏菜单结构、不改后端、不改路由表。

## 7. 依赖

- vue-router（useRoute/useRouter，已有）。
- Element Plus（el-icon 关闭图标，已有）。
- vitest（FundSelect 已建配置，复用 `frontend/vitest.config.js`）。
- `Layout.vue`（集成点）。

## 8. 风险评估

- **父菜单路由误成 tab**：靠「有组件才成 tab」过滤（isParent 无组件）。
- **关闭当前 tab 后跳转**：右侧优先 -> 左侧 -> 首页，保证不空。
- **刷新丢失 tab 状态**：本期接受（仅首页留存），持久化作后续。
- **tab 溢出**：tab 多时横向滚动（overflow-x），不挤垮布局。

## 9. Open Questions（Phase 3 已澄清）

- **tab 含义**：多标签页 TagsView（顶栏 tab，访问过页面成 tab，切换/关闭）。
- **关闭行为**：右键菜单关闭当前/其他/全部 + 首页固定。
- **刷新持久化**：本期不持久化（刷新重置为首页），后续可加 localStorage。
- **刷新按钮**：本期不做。
- **feature slug**：`tags-view`。
