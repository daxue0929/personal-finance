# 前端设计规范：多标签页 TagsView（tags-view）

> 本规范作为 Phase 6 质量审查的对照基线。本功能是「在 Layout 加一行 tab 栏」性质，设计目标是**与既有 Layout 顶栏/Element Plus 界面一致**，不引入新视觉风格。

## 1. 设计目标与原则

- **一致性优先**：TagsView 栏在视觉上紧贴既有 el-header（同高/同边框/白底），不突出、不另类。
- **复用 EP 默认**：tab 用 EP 主色（#409EFF）作激活态，关闭用 el-icon Close，不自定义色板。
- **遵循项目约定**：composable 放 `src/composables/`（与 useEChart 一致）；`<script setup>` + `<style scoped>`；逻辑抽 composable 可单测（与 useFundSearch 同构）。

## 2. 色彩规范

- 沿用 EP 默认主题，不新增色板。
- tab 栏背景 `#fff`，底部边框 `1px solid #eee`（与 el-header 一致）。
- 激活 tab：边框 + 文字 `#409EFF`（EP 主色），浅蓝底 `rgba(64,158,255,0.08)`。
- 非激活 tab：文字 `#303133`，边框 `#dcdfe6`，hover 文字 `#409EFF`。
- 关闭 × ：`#909399`，hover `#f56c6c`（与退出登录按钮 hover 同色）。
- 右键菜单：白底卡片，`box-shadow` EP 默认 popover 阴影，选项 hover `#f5f7fa`。

## 3. 字体规范

- 沿用 EP 默认字体栈，tab 文字 13px（略小于顶栏标题 16px，区分层级），不引入新字体。

## 4. 组件规范

### 4.1 TagsView 栏（容器）

| 项 | 值 |
|---|---|
| 位置 | Layout 的 el-header 与 el-main 之间，独立一行 |
| 高度 | `40px` |
| 背景 | `#fff`，底部 `1px solid #eee` |
| 内边距 | `0 16px`，flex 左对齐 |
| 溢出 | tab 多时 `overflow-x: auto`，横向滚动（不挤垮布局） |
| 显示条件 | 始终显示（在 Layout 内）；登录页不在 Layout，自然不显示 |

### 4.2 单个 tab

| 项 | 值 |
|---|---|
| 形态 | 圆角小标签（`border-radius: 3px`，`border: 1px solid`），padding `4px 10px` |
| 内容 | 标题文字（route.meta.title）+ 关闭 ×（affix tab 无 ×） |
| 激活态 | 边框/文字 #409EFF + 浅蓝底 |
| 交互 | 单击切换路由；× 单击关闭；右键弹菜单 |
| 关闭 × | 仅 hover 该 tab 时显示（affix tab 永不显示） |

### 4.3 右键上下文菜单

- 触发：tab 上 `@contextmenu.prevent` 弹出定位菜单。
- 选项：关闭当前 / 关闭其他 / 关闭全部（固定 tab 不被关）。
- 关闭当前：若关的是活跃 tab，跳相邻（右优先 -> 左 -> 首页）。
- 菜单定位：跟随鼠标 `clientX/clientY`，点击他处或滚动即关。

### 4.4 首页固定 tab

- 首页 = `/portfolio`（持仓看板），初始化即入 tabs，标记 `affix: true`。
- affix tab：无 ×、右键菜单不对其生效（关闭当前/其他/全部都跳过 affix）。

## 5. 结构（composable 分离，可单测）

```
TagsView.vue            视图层（薄）：渲染 tabs / click / close / contextmenu / watch route
  └─ useTagsView.js     逻辑层（composable）：tabs 状态 + addTab/closeTab/closeOthers/closeAll
       └─ （无外部依赖，纯响应式状态）
```

- 逻辑层可独立单测（vitest，注入初始 tabs，验证 add 去重 / close 跳转 / closeOthers / closeAll / affix 保留）。
- 视图层薄测可选（jsdom mock router）。

## 6. 测试规范（TDD）

- 配置：复用既有 `frontend/vitest.config.js`（jsdom，include `src/**/*.{spec,test}.js`）。
- **先写测试再实现** `src/composables/useTagsView.spec.js`（约 8 例）：
  - 初始含首页 affix tab；
  - addTab 新路由 -> tabs +1；重复路由 -> 不增；
  - addTab 跳过无组件的父路由（mock isParent）；
  - closeTab 非活跃 tab -> tabs -1，活跃路由不变；
  - closeTab 活跃 tab -> 返回建议跳转的相邻 path；
  - closeOthers -> 仅留当前 + affix；
  - closeAll -> 仅留 affix；
  - affix tab 不可关（closeTab 对 affix 无效）。
- 跑 `npm run test`（vitest run）通过。

## 7. 一致性检查清单（Phase 6 对照）

- [ ] TagsView 栏高度 40 / 白底 / 底边框，紧贴 el-header 风格
- [ ] 激活 tab 用 EP 主色 #409EFF + 浅蓝底，非激活灰边
- [ ] 关闭 × 仅 hover 显示，affix 无 ×
- [ ] 右键菜单：关闭当前/其他/全部，affix 不被关
- [ ] 首页 tab 固定始终在
- [ ] tab 溢出横向滚动
- [ ] composable 放 composables/，与 useEChart 一致
- [ ] vitest 测试先于实现并通过
- [ ] `npm run build` 通过，`dist/` 提交
