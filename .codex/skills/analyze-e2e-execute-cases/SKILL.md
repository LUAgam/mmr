---
name: analyze-e2e-execute-cases
description: 分析并处理 `python run_e2e.py execute-cases` 产生的失败或异常用例。输入参数为 `session_name`，并支持可选 `cases` 编号列表；基于 `runs/session_name/e2e_case_execution/manifest.json`、`test_steps.md`、`test_report.md`、`attempt_*` 产物、`cursor_agent_logs` 和相关源码，先输出根因判断、证据链、受影响仓库/代码位置，再对可明确收敛为 `oms_code_bug` 的问题执行最小修复与验证。适用于复盘 `failed` / `infra_failed` case、检查自动修复为何未生效、或需要把测试现象收敛到具体代码层并推动修复时。
---

# Analyze E2E Execute Cases

## 快速开始

1. 接收用户提供的 `session_name`，并支持可选的 `cases` 编号列表。
2. 在仓库根目录执行：

```bash
python ./.codex/skills/analyze-e2e-execute-cases/scripts/collect_e2e_failure_context.py \
  --project-root "$PWD" \
  --session-name <session_name>
```

若用户只想分析部分 case，追加：

```bash
  --cases 1.2,1.6
```

3. 不传 `--cases` 时，默认分析当前 session 下全部 `failed` / `infra_failed` case。
4. 先阅读脚本输出的失败 case 清单，再按 case 逐个分析，不要一上来就全仓库盲搜。
5. 如果脚本提示找不到 `manifest.json`、`cursor_agent_logs` 或 case 产物，要先指出缺失项，再决定是否继续做有限分析。
6. 分析完成后，如果根因能够明确收敛为 `oms_code_bug`，继续进入修复；否则停止在分析结论，不要强行改代码。

## 工作流

### 第一步：定位失败 case 与证据入口

1. 读取 `runs/session_name/e2e_case_execution/manifest.json`。
2. 如果用户传了 `cases`，只分析指定编号；如果没传，则处理全部 `failed` / `infra_failed` case。
3. 对每个失败 case，至少核对这些文件：
   - `execution_result.json`：看最终状态、摘要、错误信息。
   - `test_report.md`：看实际执行事实、日志分析、最终结论。
   - `test_steps.md`：看测试目标、执行路径、关键校验点。
   - `attempt_*_failure_summary.md`：看失败收敛过程。
   - `attempt_*_fix_report.md` / `attempt_*_ai_result.json`：看历史自动修复判断、受影响仓库、未继续重试原因。
   - `cursor_agent_logs/*.log`：看 agent 实际调用、报错原文、工具执行轨迹。
4. 优先使用辅助脚本输出的 `related_cursor_logs`，不要手工把所有日志全部读一遍。

### 第二步：建立根因判断

按下面顺序收敛：

1. 先判断失败属于哪一类：
   - `oms_code_bug`
   - `test_asset_issue`
   - `e2e_tooling_issue`
   - `environment_issue`
   - `non_oms_behavior`
   - `unknown`
2. 结论必须由证据支撑，至少引用两类材料，通常是：
   - 测试报告 / 失败摘要
   - agent 日志
   - 源码
3. 若 `test_report.md` 已经给出日志分析，不要机械复述，要检查它与源码、修复报告是否一致。
4. 若自动修复曾经修改过代码但最终 `retry_recommended = false`，重点分析：
   - 修复是否改对仓库；
   - 修复是否真正命中运行路径；
   - 构建/热更是否真的生效；
   - 页面或接口复验为什么仍然不满足预期。

### 第三步：结合源码定位

1. 用 `rg` 优先搜索这些线索：
   - 测试报告中的页面文案、接口名、错误文案、字段名、组件名。
   - `fix_report.md` 中提到的仓库名、文件名、类名、方法名。
   - `ai_result.json` 中的 `affected_repos`。
2. 根据失败类型缩小范围：
   - 建链页/详情页/弹窗/展示口径问题：先查 `workdir/oms-ui`。
   - 预检查、项目创建、项目详情、状态流转问题：先查 `workdir/ghana` 及相关后端仓库。
   - Playwright、上传、agent 调用失败：先查测试基建和工具链，再判断是否是环境问题。
3. 找到代码后，不只说明“怀疑这里有问题”，要说明：
   - 当前逻辑做了什么；
   - 为什么会导致本次 case 失败；
   - 最小修复应该落在哪一层。
4. 如果证据不足以收敛到具体文件，要明确缺口，不要编造代码结论。

### 第四步：给出修复建议

修复建议要具体到“可执行”，并且在以下前提同时满足时，直接进入修复：

1. 根因已经明确收敛为 `oms_code_bug`。
2. 能定位到候选仓库与较小的改动面。
3. 不需要大规模重构或高风险删除。

若不满足以上条件，只输出修复建议，不执行改动。

每个失败 case 至少给出：

1. `根因分类`
2. `证据链`
3. `候选仓库`
4. `候选文件/函数/组件`
5. `建议修复方向`
6. `建议验证方式`
7. `风险与未决问题`

若判断不是 `oms_code_bug`，修复建议应改为“下一步排查/补齐动作”，例如：

- 补测试资产
- 修测试脚本
- 修环境
- 追加日志采样
- 明确产品预期

### 第五步：执行修复与验证

只有在确认是 `oms_code_bug` 时，才执行这一阶段。

1. 基于前面的证据链，只做最小必要改动，不要顺手扩大范围。
2. 不要修改 `test_steps.md`、`test_report.md`、`execution_result.json`、`attempt_*` 这类测试产物来掩盖问题。
3. 优先修业务代码或真正的测试基建代码，不要通过绕过校验、删除断言、篡改报告来“修复”。
4. 修复完成后至少做一种验证：
   - 相关测试/脚本验证
   - 最小构建验证
   - 与 case 直接相关的人工/日志验证
5. 如果当前环境无法完整回归 E2E，也要明确说明：
   - 实际改了什么
   - 已做了哪些局部验证
   - 哪些步骤仍需人工或后续环境复验
6. 若修复过程中发现最初判断不成立，应停止修改，回到分析结论并明确纠偏原因。

## 输出要求

对用户输出时，先给结论，再给证据，不要先铺长背景。若实际执行了修复，输出中必须同时包含“分析结论”和“实际修复结果”。

推荐使用下面的结构：

```markdown
## session 概览
- session_name: `...`
- 失败/异常 case 数: `...`
- 分析范围: `全量 | 指定 case`

## case1.x 标题
- 结论: `oms_code_bug | test_asset_issue | e2e_tooling_issue | environment_issue | non_oms_behavior | unknown`
- 核心判断: 1-2 句
- 证据:
  - `test_report.md`: ...
  - `cursor_agent_logs/...log`: ...
  - `源码路径`: ...
- 修复建议: ...
- 实际修复: `已修复 | 未修复`
- 修复内容: ...
- 验证结果: ...
- 验证建议: ...
- 未决问题: ...
```

如果用户只要求“找出报错 case”，先列 case 清单与失败摘要；如果用户要求“分析原因”，再展开证据链和修复建议。若用户指定了 `cases`，输出中要明确说明当前是“定向分析”而不是全量分析。若实际未执行修复，也要明确说明未修复原因。

## 注意事项

1. 不要把 `infra_failed` 直接等同于环境问题；先看是 Cursor API、Playwright、上传、SSH、构建还是项目代码路径引起。
2. 不要仅凭一次自动修复失败就断言源码结论错误；要检查修复是否命中真实运行路径。
3. 不要把测试报告里的推断当事实，必须二次核对源码或日志。
4. 不要修改 `test_steps.md`、`test_report.md`、`execution_result.json` 这类测试产物来“修复”问题。
5. 若结论不是 `oms_code_bug`，或者修复风险明显过高，要明确停止修复，不要为了“完成任务”硬改代码。

## 资源

- 辅助脚本：`scripts/collect_e2e_failure_context.py`
  用于根据 `session_name` 汇总失败 case、产物路径和关联 cursor agent 日志，并支持按 `cases` 过滤。
- 参考文档：`references/artifact-map.md`
  用于快速理解各类产物的语义与推荐阅读顺序。
