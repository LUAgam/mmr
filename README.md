# MMR（多模型评审）目录说明

本仓库提供一套 **「方案 → 方案复审 → 执行 → 两轮代码复审」** 的多 Agent 工作流，用于在主 Agent 会话里按阶段调用，减少单次改动的遗漏与回归风险。

当前同时支持：

- **Cursor**：通过 `.cursor/agents/*.md` 与 `.cursor/rules/*.mdc` 使用。
- **Codex**：通过 `.codex/agents/*.toml`、`.codex/config.toml` 与 `AGENTS.md` 使用。

---

## 目录结构

| 路径 | 作用 |
|------|------|
| `.cursor/rules/mmr-subagent-safety.mdc` | Cursor 调度约束、默认串行流程、可中断条件、最终回复结构 |
| `.cursor/agents/mmr-planner.md` | Cursor 方案制定（改代码前输出可执行实施方案） |
| `.cursor/agents/mmr-plan-reviewer.md` | Cursor 方案复审（P0/P1/P2 问题清单） |
| `.cursor/agents/mmr-executor.md` | Cursor 按已确认方案做最小必要改动与校验 |
| `.cursor/agents/mmr-code-reviewer-gpt.md` | Cursor 代码复审 A：正确性、回归风险 |
| `.cursor/agents/mmr-code-reviewer-gemini.md` | Cursor 代码复审 B：边界、契约、一致性、隐性风险 |
| `.codex/config.toml` | Codex 项目级 agent 并发/嵌套深度配置 |
| `.codex/agents/*.toml` | Codex custom agents，对应 Cursor 侧 5 个 MMR agent |
| `AGENTS.md` | Codex 主 Agent 加载的 MMR 调度规则 |

---

## Cursor 使用方式

### 1. 让 Cursor 识别 agents 与 rules

- **做法 A（常见）**：把本目录下的 `.cursor/agents/*.md` 与 `.cursor/rules/mmr-subagent-safety.mdc` 放到**你实际开发的项目仓库**根目录的 `.cursor/agents/`、`.cursor/rules/` 中。
- **做法 B**：若你的工作区根目录就是本 `mmr` 文件夹，则保持现有 `mmr/.cursor/agents`、`mmr/.cursor/rules` 结构即可。

子代理在 Cursor 里以 frontmatter 中的 `name` 字段为准，对应名称为：

`mmr-planner`、`mmr-plan-reviewer`、`mmr-executor`、`mmr-code-reviewer-gpt`、`mmr-code-reviewer-gemini`。

### 2. Cursor 模型说明

Cursor 侧模型保留原始配置：

- `mmr-planner`：`gpt-5.4-medium`
- `mmr-plan-reviewer`：`gemini-3.1-pro`
- `mmr-executor`：`composer-2`
- `mmr-code-reviewer-gpt`：`gpt-5.4-medium`
- `mmr-code-reviewer-gemini`：`gemini-3.1-pro`

---

## Codex 使用方式

### 1. 让 Codex 识别 agents 与规则

把以下文件复制到实际开发项目根目录：

```text
.codex/config.toml
.codex/agents/mmr-planner.toml
.codex/agents/mmr-plan-reviewer.toml
.codex/agents/mmr-executor.toml
.codex/agents/mmr-code-reviewer-gpt.toml
.codex/agents/mmr-code-reviewer-gemini.toml
AGENTS.md
```

如果你的 Codex 工作区根目录就是本仓库，则保持现有结构即可。

### 2. Codex 模型说明

Codex 侧使用 Codex custom agent TOML 格式，并将模型路由固化在 `.codex/agents/*.toml` 中：

| Agent | 默认模型 | 权限 |
|---|---|---|
| `mmr-planner` | `gpt-5.4` | `read-only` |
| `mmr-plan-reviewer` | `gpt-5.4` | `read-only` |
| `mmr-executor` | `gpt-5.3-codex` | `workspace-write` |
| `mmr-code-reviewer-gpt` | `gpt-5.4` | `read-only` |
| `mmr-code-reviewer-gemini` | `gpt-5.4` | `read-only` |

说明：

- Codex 版默认不直接使用 Cursor 专用的 `composer-2`。
- `mmr-code-reviewer-gemini` 保留原流程命名，但默认模型使用 `gpt-5.4`，避免官方 OpenAI provider 下无法解析 Gemini 模型名。
- 如果你通过 OpenRouter/中转站配置了 Gemini，可自行把 `.codex/agents/mmr-code-reviewer-gemini.toml` 中的 `model` 改成你的 provider 支持的模型名。
- `model_provider`、`model_providers`、API key、profile 等机器本地配置应放在 `~/.codex/config.toml`，不要放进项目级配置。

### 3. Codex 项目级配置

`.codex/config.toml` 默认只放项目级 agent 控制：

```toml
[agents]
max_threads = 6
max_depth = 1
job_max_runtime_seconds = 1800
```

其中 `max_depth = 1` 用于贴合 MMR 的“禁止嵌套 subagent”约束。

---

## 默认 MMR 流程

当用户需求属于 **修 bug / 修问题 / 一次性完成修复和 review / 不要频繁交互** 时，主 Agent 应按规则顺序：

1. `mmr-planner` — 最小修复方案
2. `mmr-plan-reviewer` — 复审方案
3. 无 P0 阻塞 → `mmr-executor` — 改代码
4. `mmr-code-reviewer-gpt` — 第一轮代码复审（只读，不改代码）
5. `mmr-code-reviewer-gemini` — 第二轮代码复审（只读）
6. 向用户汇总（格式见下）

**硬约束**：每阶段只调当前指定的 custom agent；**禁止嵌套 subagent**；除非用户明确要求，**不要**随便起内置 subagent；review 类 **不得改代码**；executor **不得擅自重做设计**。

若某个 custom agent 不可用，主 Agent 应**回退为自执行**并明确说明发生了回退。

---

## 用户提示模板（可复制）

将下面整段贴到对话开头，再在末尾补上 **复现步骤 / 报错 / 期望行为** 等具体问题描述即可触发完整 MMR。

```text
请按 MMR 流程一次性完成这个 bug 的修复和 review，不要频繁与我交互。

执行要求：
1. 先调用 mmr-planner 分析问题并输出最小修复方案
2. 再调用 mmr-plan-reviewer 复审方案
3. 若无 P0 阻塞，直接调用 mmr-executor 修改代码
4. 修改完成后，依次调用：
   - mmr-code-reviewer-gpt
   - mmr-code-reviewer-gemini
5. 最后一次性汇总输出：
   - 问题理解
   - 根因分析
   - 最终修复方案
   - 实际改动文件
   - 校验结果
   - GPT 复审结论
   - Gemini 复审结论
   - 最终风险与建议
   - 是否建议提交

额外要求：
- 不要启动 built-in subagents
- 不要做嵌套 subagent
- 除非遇到 P0 风险或明显高风险阻塞，否则不要中途向我确认
- 优先最小改动、低回归风险、可验证
```

---

## 最终给用户的输出结构

主 Agent 最终回复须包含：

## 问题理解
## 根因分析
## 最终修复方案
## 实际改动文件
## 校验结果
## GPT 复审结论
## Gemini 复审结论
## 最终风险与建议
## 是否建议提交

---

## 允许中途停下来问人的情况

仅当：方案复审 **P0** 且难以小范围收敛、执行阶段高风险阻塞且范围显著扩大、核心重构影响面大、缺关键上下文、或测试/构建表明方向可能错误等。其余情况应默认跑完流程，避免频繁确认。
