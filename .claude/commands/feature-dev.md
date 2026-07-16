---
description: 引导式功能开发（项目级叠加层：动态引用插件版 7 阶段 + 强制子流程门禁，不重复官方内容）
argument-hint: 可选：功能描述
---

# Feature Development（项目级叠加层）

> 本命令**不重复**插件版 feature-dev 的 7 阶段主体，只在加载它之后，叠加 `CLAUDE.md`「Feature Development 强制子流程」的强制条款与前置门禁。这样官方流程主体可随插件更新，本文件只保有项目专属的增量约束，定制部分一目了然。

## 第一步：加载插件版流程主体

先用 Bash 定位当前生效（mtime 最新）的插件版 feature-dev 命令：

```bash
ls -t ~/.claude/plugins/cache/claude-plugins-official/feature-dev/*/commands/feature-dev.md 2>/dev/null | head -1
```

- 把返回的路径用 Read 读入，**以其 7 阶段**（Discovery -> Codebase Exploration -> Clarifying Questions -> Architecture Design -> Implementation -> Quality Review -> Summary）**为流程主体**，遵循其中的阶段定义、agent 调用方式与核心原则。
- 若上述命令无返回（插件路径变动），则退回遵循 `CLAUDE.md` 的「Feature Development 强制子流程」条款，并提示用户插件版 feature-dev 未找到。

## 第二步：叠加以下强制条款（不可跳过、不可降级）

在执行插件版各阶段时，必须**额外**满足：

### Phase 1: Discovery
- ⛔ **强制**：执行 `/create-prd` 流程，产出 `tasks/prd-[feature].md`（含功能目标 / 用户故事 / 验收标准 / 非目标 / 依赖 / 风险）。先就上述要素提问、等用户回答再生成。
- **不得**用对话层的「总结理解并确认」代替落盘 PRD--确认是对话层，PRD 是文件，两者都要。

### Phase 3: Clarifying Questions
- 澄清结果回写进 `tasks/prd-[feature].md` 的「Open Questions」。

### Phase 4: Architecture Design
- ⛔ **强制（涉及前端界面时）**：执行 `/frontend-design` 流程，产出 `tasks/design-[feature].md`（色彩 / 字体 / 组件规范）。
- 「是否涉及前端」由用户在确认方案时**明示**；只要有 `frontend/src/` 下的 UI 新增或改动即触发，模型**不得**自行判定为「纯后端」以跳过本步。

### Phase 5: Implementation —— 前置门禁
开始编码前**必须全部满足**，缺失任一项则**停下提示用户补齐**，不得自行继续：
1. `tasks/prd-[feature].md` 已存在且内容完整；
2. 涉及前端时 `tasks/design-[feature].md` 已存在；
3. 用户已对架构方案（及前端设计）给出**明确批准**。

实现阶段另需遵守：
- **测试先行（TDD）**：先写测试用例（明确预期行为与边界），再写实现，最后跑通。禁止「先实现后补测试」。
- **前端构建门禁**：改动过 `frontend/src/` 下任意文件后，`git push` 前必须在 `frontend/` 执行 `npm run build`，并把更新后的 `dist/` 一并提交（服务器靠 `git pull` 拿 `dist/` 部署）。

### Phase 6: Quality Review
- ⛔ **涉及前端时**：必须对照 `tasks/design-[feature].md` 检查实现是否符合设计规范，不符合则**返工**，不留到后面。

## 反模式（明确禁止）

- 跳过 `/create-prd`，仅用对话确认充当需求文档。
- 自行判定「纯后端」以跳过 `/frontend-design`。
- Phase 5 门禁未通过就开始写代码。
- 先实现后补测试。
- 改了 `frontend/src/` 却不 `npm run build` / 不提交 `dist/` 就 push。
