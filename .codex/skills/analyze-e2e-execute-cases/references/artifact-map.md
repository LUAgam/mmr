# execute-cases 产物地图

## 推荐阅读顺序

1. `runs/<session_name>/e2e_case_execution/manifest.json`
2. 单 case 的 `execution_result.json`
3. 单 case 的 `test_report.md`
4. 单 case 的 `test_steps.md`
5. `attempt_*_failure_summary.md`
6. `attempt_*_fix_report.md`
7. `attempt_*_ai_result.json`
8. `runs/<session_name>/cursor_agent_logs/*.log`
9. 相关源码

## 各文件语义

### manifest.json

整次 `execute-cases` 的聚合入口。优先从这里拿：

- 失败 case 列表
- `summary` / `error_message`
- `logs_analysis_performed`
- 自动修复尝试记录 `attempts`
- `report_file` / `result_file` / `steps_file`

### execution_result.json

单 case 最终结果，适合确认：

- 最终 `execution_outcome`
- 最终摘要
- 主错误信息
- 结果文件路径是否一致

### test_report.md

最重要的人类可读证据。重点关注：

- 实际执行到了哪一步
- 哪些证据来自 UI、接口、数据库或服务器日志
- 最终 FAIL / INFRA_FAIL 的直接理由
- 是否已经做过服务端日志分析

### test_steps.md

用于理解 case 原始意图与校验口径，避免把“未实现的期望”误判为 bug。

### attempt_*_failure_summary.md

记录某一轮失败后的压缩摘要，适合快速进入上下文。

### attempt_*_fix_report.md

若自动修复执行过，这里通常会说明：

- 根因判断
- 是否归类为 `oms_code_bug`
- 修改了哪个仓库
- 构建/热更是否执行
- 为什么不建议继续重试

### attempt_*_ai_result.json

结构化修复结论，重点看：

- `failure_category`
- `affected_repos`
- `fix_summary`
- `retry_recommended`
- `stop_reason`

### cursor_agent_logs/*.log

用于还原 agent 真实执行轨迹。重点看：

- 原始 prompt 中的 case_id、路径、约束
- tool call 轨迹
- 最终错误原文
- 是否是 Cursor API / Playwright / SSH / 构建失败

## 常见判断信号

### 更像 OMS 代码 bug

- 测试报告、服务端日志、源码三者能对齐到同一个功能缺口。
- 自动修复报告已经明确到受影响仓库和代码路径。
- UI、接口或后端逻辑表现稳定复现，与环境偶发性无关。

### 更像环境或工具链问题

- `cursor_agent_logs` 中直接出现 Cursor API、网络、Playwright、SSH、上传、构建链路失败。
- `test_report.md` 明确说明 case 没有跑到产品行为验证阶段。
- 失败并非业务逻辑不符合预期，而是执行工具无法完成动作。

### 更像测试资产或预期问题

- `test_steps.md` / case list 的预期与产品当前口径不一致。
- 报告里能看到“当前环境不存在对应端点/数据/对象”。
- 现象无法在源码层形成稳定闭环。
