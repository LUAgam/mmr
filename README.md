# MMR（多模型评审）目录说明

本目录提供一套 **「方案 → 方案复审 → 执行 → 两轮代码复审」** 的 **Cursor custom subagent** 与 **always-on 规则**，并补充了一套 **E2E 失败用例“双模型分析 → 执行 → 验证”** 提示词与依赖 skill，便于在主 Agent 会话里按阶段调用，减少单次改动的遗漏与回归风险。

规则全文见：`.cursor/rules/mmr-subagent-safety.mdc`（`alwaysApply: true` 时会对工作区内主 Agent 生效，具体以 Cursor 对 rules 的加载方式为准）。

---

## 目录结构

| 路径 | 作用 |
|------|------|
| `.cursor/rules/mmr-subagent-safety.mdc` | 调度约束、默认串行流程、可中断条件、最终回复结构 |
| `.cursor/agents/mmr-planner.md` | 方案制定（改代码前输出可执行实施方案） |
| `.cursor/agents/mmr-plan-reviewer.md` | 方案复审（P0/P1/P2 问题清单） |
| `.cursor/agents/mmr-executor.md` | 按已确认方案做最小必要改动与校验 |
| `.cursor/agents/mmr-analyze-gpt.md` | E2E 失败分析 A：基于证据收敛根因 |
| `.cursor/agents/mmr-analyze-gemini.md` | E2E 失败分析 B：从反证与风险角度交叉分析 |
| `.cursor/agents/mmr-execute.md` | E2E 综合结论后的最小必要修改执行 |
| `.cursor/agents/mmr-verify.md` | E2E 修改后的构建、热更、case 重跑验证 |
| `.cursor/agents/mmr-code-reviewer-gpt.md` | 代码复审 A：正确性、回归风险 |
| `.cursor/agents/mmr-code-reviewer-gemini.md` | 代码复审 B：边界、契约、一致性、隐性风险 |
| `.cursor/prompts/mmr-dual-analyze-execute-cases.md` | E2E 失败 case 的双模型分析与执行主提示词 |
| `.codex/skills/analyze-e2e-execute-cases/` | E2E 失败 case 汇总脚本、skill 说明与产物阅读参考 |

---

## 使用方式

### 1. 让 Cursor 识别 agents 与 rules

- **做法 A（常见）**：把本目录下的 `.cursor/agents/*.md` 与 `.cursor/rules/mmr-subagent-safety.mdc` 放到**你实际开发的项目仓库**根目录的 `.cursor/agents/`、`.cursor/rules/` 中（与 Cursor 项目约定一致）。
- **做法 B**：若你的工作区根目录就是本 `mmr` 文件夹，则保持现有 `mmr/.cursor/agents`、`mmr/.cursor/rules` 结构即可。

子代理在 Cursor 里以 frontmatter 中的 `name` 字段为准，对应名称为：

`mmr-planner`、`mmr-plan-reviewer`、`mmr-executor`、`mmr-code-reviewer-gpt`、`mmr-code-reviewer-gemini`、`mmr-analyze-gpt`、`mmr-analyze-gemini`、`mmr-execute`、`mmr-verify`。

### 2. 何时走完整 MMR 流程

当用户需求属于 **修 bug / 修问题 / 一次性完成修复和 review / 不要频繁交互** 时，主 Agent 应按规则顺序：

1. `mmr-planner` — 最小修复方案  
2. `mmr-plan-reviewer` — 复审方案  
3. 无 P0 阻塞 → `mmr-executor` — 改代码  
4. `mmr-code-reviewer-gpt` — 第一轮代码复审（只读，不改代码）  
5. `mmr-code-reviewer-gemini` — 第二轮代码复审（只读）  
6. 向用户汇总（格式见下）

**硬约束（摘自规则）**：每阶段只调当前指定的 custom subagent；**禁止嵌套 subagent**；除非用户明确要求，**不要**随便起内置 subagent（如 Explore、Browser、Bash）；review 类 **不得改代码**；executor **不得擅自重做设计**。

若某个 custom subagent 不可用，主 Agent 应**回退为自执行**并明确说明发生了回退。

### 3. 用户提示模板（可复制）

将下面整段贴到对话开头，再在末尾补上 **复现步骤 / 报错 / 期望行为** 等具体问题描述即可触发完整 MMR。汇总小节名称须与 `mmr-subagent-safety.mdc` 一致（已写在模板第 5 条）。

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

### 4. 最终给用户的输出结构

与上表第 5 条及 `mmr-subagent-safety.mdc` 相同，主 Agent 最终回复须包含：**问题理解、根因分析、最终修复方案、实际改动文件、校验结果、GPT 复审结论、Gemini 复审结论、最终风险与建议、是否建议提交**。

### 5. E2E 失败用例流程

若要处理 `run_e2e.py execute-cases` 产生的失败 case，可直接使用：

- `.cursor/prompts/mmr-dual-analyze-execute-cases.md`

该提示词会串联：

1. `mmr-analyze-gpt`
2. `mmr-analyze-gemini`
3. `mmr-execute`
4. `mmr-verify`

相关辅助资源位于：

- `.codex/skills/analyze-e2e-execute-cases/SKILL.md`
- `.codex/skills/analyze-e2e-execute-cases/scripts/collect_e2e_failure_context.py`
- `.codex/skills/analyze-e2e-execute-cases/references/artifact-map.md`

### 6. 允许中途停下来问人的情况

仅当：方案复审 **P0** 且难以小范围收敛、执行阶段高风险阻塞且范围显著扩大、核心重构影响面大、缺关键上下文、或测试/构建表明方向可能错误等（详见规则文件）。其余情况应默认跑完流程，避免频繁确认。

---
