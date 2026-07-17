---
description: 引导式功能开发（项目级叠加层：加载插件版 7 阶段 + 强制子流程门禁，不重复官方内容）
argument-hint: 可选：功能描述
---

# Feature Development（项目级叠加层）

> 本命令**不重复**插件版 feature-dev 的 7 阶段主体，只在加载它之后，叠加项目专属的强制条款与前置门禁。这样官方流程主体可随插件更新，本文件只保有项目专属的增量约束，定制部分一目了然。

## 第一步：加载插件版流程主体

直接 Read 插件版 feature-dev 命令作为 7 阶段流程主体（Discovery -> Codebase Exploration -> Clarifying Questions -> Architecture Design -> Implementation -> Quality Review -> Summary），遵循其中的阶段定义、agent 调用方式与核心原则。首选 marketplaces 下的稳定单文件路径（无 glob 歧义）：

```
~/.claude/plugins/marketplaces/claude-plugins-official/plugins/feature-dev/commands/feature-dev.md
```

若该路径不存在，用 Bash 退回 glob 查找，再 Read 返回的路径：

```bash
ls -t ~/.claude/plugins/cache/claude-plugins-official/feature-dev/*/commands/feature-dev.md 2>/dev/null | head -1
```

- **自检（不可跳过）**：读入后确认已拿到完整的 7 阶段定义；若两条路径都无返回或内容残缺，**停下并提示用户**「插件版 feature-dev 未找到/不完整，无法启动流程」，不得在缺少流程主体的情况下继续执行下方门禁。
- **`$ARGUMENTS` 透传**：把本次 `/feature-dev` 后传入的功能描述当作插件主体的 `$ARGUMENTS`，并同样透传给后续 `/create-prd`，不得按字面量丢弃。

## 第二步：强制条款（不可跳过、不可降级）

在执行插件版各阶段时，必须**额外**满足：

### Phase 1: Discovery
- ⛔ **强制**：执行 `/create-prd` 流程，产出 `tasks/prd-[feature].md`（含功能目标 / 用户故事 / 验收标准 / 非目标 / 依赖 / 风险）。先就上述要素提问、等用户回答再生成。
- **定 feature slug（一处定、处处用）**：产出 PRD 时即与用户敲定本功能的 `[feature]` slug--**kebab-case、纯小写、连字符分隔**（如 `fund-seller`、`position-analysis`、`fund-code-search-select`），不得用下划线 / 大写 / 中文。该 slug 写入 PRD 文件名（`prd-[feature].md`）并在 PRD 正文顶部记一行「**Feature slug**: `[feature]`」，作为后续所有文件的唯一命名来源：
  - 设计文档：`tasks/design-[feature].md`
  - 任务清单：`tasks/tasks-[feature].md`
  - 测试文件：`data-crawler/tests/test_[feature].py`（Python 文件名规则要求下划线，故 slug 中的连字符转下划线，如 `fund-seller` -> `test_fund_seller.py`）
- **不得**用对话层的「总结理解并确认」代替落盘 PRD--确认是对话层，PRD 是文件，两者都要。

### Phase 2: Codebase Exploration

> 本项目经转发模型访问，后台 agent 的通知链路不可靠，曾出现「子 agent 已结束、主任务一直挂」。故 agent 调用一律走同步模式，不依赖通知。

- **同步串行发起（防卡死，强制）**：用同步模式（`run_in_background: false`）起 explorer agent。同步调用会阻塞到返回，**多个 agent 在一条回复内会排队执行、非真并行**——这是有意取舍：换来不依赖通知机制、对转发模型稳定。控制 agent 数量在 1–2 个（见下方降级），避免串行累积耗时。
- **禁止**：后台模式（`run_in_background: true`）+ 轮询 / `TaskOutput` 阻塞等待；起完 agent 后本轮空转说「我在等 agent」。
- **按规模降级**：大改（新功能 / 跨后端 + 前端）起 2 个 explorer；中改起 1 个；小改（单文件 / 单层 / 纯 SQL）**主任务直接 Read**，不起 agent。
- **聚焦切分**：后端按层给一个（storage 层 + task 层 + web 入口），前端给一个（api 模块 + views）。
- **锚点优先**：本项目多为「照一个已有 feature 改」，优先让 agent 以 `tasks/` 下相似的 `prd-`/`design-` 文档为锚点回溯，避免全库扫描。
- **限返回 + 主任务读回**：每个 agent 只回 5–10 个关键文件 + 一句话摘要；长文由主任务用 Read 读回，不得只凭摘要推进。
- **超时降级**：若某个 agent 返回空 / 超时，主任务用已有信息继续并提示用户「XX 视图探索缺失」，不无限等待。

### Phase 3: Clarifying Questions
- 澄清结果回写进 `tasks/prd-[feature].md` 的「Open Questions」。

### Phase 4: Architecture Design
- ⛔ **强制（涉及前端界面时）**：执行 `/frontend-design` 流程，产出 `tasks/design-[feature].md`（色彩 / 字体 / 组件规范），`[feature]` 用 Phase 1 敲定的 slug。`/frontend-design` 插件只给设计指导、不负责落盘文件名，故文件名由本层强制：必须为 `design-[feature].md`，**不得**用通用 `DESIGN.md`。
- 「是否涉及前端」由用户在确认方案时**明示**；只要涉及 `frontend/src/` 下新增或重排可视觉组件即触发（仅改样式常量、调路由 meta.sort 等非可视觉改动不触发）
- 架构方案获用户**明确批准**后，执行 `/generate-tasks tasks/prd-[feature].md`，产出 `tasks/tasks-[feature].md`（分层任务清单 + 待建/改/测文件清单），`[feature]` 用 Phase 1 敲定的 slug。该命令默认会据 PRD 文件名派生输出名（可能落成 `tasks-prd-[feature].md`），**须显式改名为** `tasks/tasks-[feature].md`。命令交互式分两步（先出高层任务、等用户回 "Go"、再出子任务），按其节奏走完，不得跳步。

### Phase 5: Implementation —— 前置门禁
开始编码前**必须全部满足**，缺失任一项则**停下提示用户补齐**，不得自行继续：
1. `tasks/prd-[feature].md` 已存在且内容完整（完整 = 含功能目标 / 用户故事 / 验收标准 / 非目标四节，且非占位符空壳）；
2. 涉及前端时 `tasks/design-[feature].md` 已存在；
3. `tasks/tasks-[feature].md` 已存在且内容完整（由 `/generate-tasks` 产出）。若该文件缺失或不完整，提示用户「先走完 `/generate-tasks` 的两步交互（高层任务 -> 回 "Go" -> 子任务）」补齐，**不判为门禁失败**、不自行编造任务清单；
4. 用户已对架构方案（及前端设计）给出**明确批准**。

实现阶段另需遵守：
- **`/implement-tasks` 职责收窄 + TDD 节奏**：用 `/implement-tasks tasks/tasks-[feature].md` 管理「任务勾选进度 + 待建/改/测文件清单 + 依赖顺序」，但**不照搬命令自带的实现节奏**。该命令默认按 Pre-Implementation -> Implementation -> Testing -> Cleanup 推进（实现优先、测试归到后面），与本流程冲突。**每个任务的实现顺序一律按 TDD**：先在 `data-crawler/tests/test_<feature>.py` 写该任务相关用例（明确预期与边界） -> 再写实现 -> 在 `data-crawler/` 下跑 `python3 -m pytest tests/test_<feature>.py -q` 通过 -> 勾选该任务。命令的 Pre-Implementation（读任务、查依赖、定文件）和 Cleanup（清理临时代码、回写勾选）环节可保留。
- **测试先行禁令**：禁止「先实现后补测试」。上述 TDD 四步为硬性顺序，不得跳过写用例直接实现。
- **前端构建门禁**：改动过 `frontend/src/` 下任意文件后，`git push` 前必须在 `frontend/` 执行 `npm run build`，并把更新后的 `dist/` 一并提交（服务器靠 `git pull` 拿 `dist/` 部署）。

### Phase 6: Quality Review
- **reviewer agent 调用纪律**：插件主体要求起 3 个 code-reviewer agent（简洁/DRY、功能正确性、项目规范）。沿用 Phase 2 的 agent 规则——同步模式（`run_in_background: false`）、不起后台、不轮询、不空转等待；**按规模降级**：大改起 2 个、中改起 1 个，小改（单文件 / 纯 SQL）主任务自审即可、不起 agent。agent 只回问题清单 + 严重度，主任务读回相关文件核实，不凭摘要下定论。
- ⛔ **涉及前端时**：必须对照 `tasks/design-[feature].md` 检查实现是否符合设计规范，不符合则**返工**，不留到后面。
- **后端质量门禁**：在 `data-crawler/` 下执行 `python3 -m pytest tests/ -q` 跑全量回归，确认无回归；并对照 `tasks/prd-[feature].md` 的验收标准逐条核对，未达标项不得收尾。

### Phase 7: Summary
- 收尾时点一遍三个流程文档的最终状态：`tasks/prd-[feature].md`（验收标准是否全部达标）、`tasks/design-[feature].md`（涉及前端时是否对照过）、`tasks/tasks-[feature].md`（任务是否全部勾选完）。
- 总结：建了什么 / 关键决策 / 改动文件清单 / 后续建议（含是否归档 `tasks/` 文档、是否需 `git push` 并按构建门禁提交 `dist/`）。

## 反模式（明确禁止）

- 跳过 `/create-prd`，仅用对话确认充当需求文档。
- 自行判定「纯后端」以跳过 `/frontend-design`。
- 架构方案批准后跳过 `/generate-tasks`，凭方案直接写代码、不产出 `tasks/tasks-[feature].md`。
- Phase 5 门禁未通过就开始写代码。
- 先实现后补测试。
- 改了 `frontend/src/` 却不 `npm run build` / 不提交 `dist/` 就 push。
- 用后台 agent（`run_in_background: true`）+ 轮询等待，导致主任务卡死（Phase 2/6 的 reviewer 同样适用）。
- Phase 6 不跑全量 `pytest tests/ -q`、不对照 PRD 验收标准就收尾。
- 把回测脚本、分析报告等非本流程产物混入 `tasks/`（`tasks/` 仅放 `prd-`/`design-`/`tasks-` 流程文档）。
