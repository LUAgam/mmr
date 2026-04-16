#!/usr/bin/env python3
"""汇总 execute-cases 失败用例的上下文入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FAIL_OUTCOMES = {"failed", "infra_failed"}
LOG_NAME_GLOB = "cursor_agent_*.log"


def parse_args() -> argparse.Namespace:
  """解析命令行参数。"""
  parser = argparse.ArgumentParser()
  parser.add_argument("--project-root", required=True, help="代码仓库根目录")
  parser.add_argument("--session-name", required=True, help="要分析的 session 名称")
  parser.add_argument(
    "--cases",
    help="可选，逗号分隔的 case 编号列表，例如 1.2,1.6；未传时分析全部失败/异常 case",
  )
  parser.add_argument("--output", help="可选，写入 JSON 文件")
  return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
  """读取 JSON 文件并校验顶层结构。"""
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"JSON 顶层不是对象: {path}")
  return data


def collect_attempt_files(case_dir: Path) -> list[str]:
  """收集当前 case 下的历史尝试产物。"""
  if not case_dir.is_dir():
    return []
  names = sorted(
    str(path)
    for path in case_dir.iterdir()
    if path.is_file() and path.name.startswith("attempt_")
  )
  return names


def find_related_logs(log_dir: Path, case_id: str, case_dir: Path) -> list[str]:
  """根据 case_id 和输出目录粗略匹配相关 agent 日志。"""
  if not log_dir.is_dir():
    return []

  markers = {
    f"case_id: `{case_id}`",
    f"case {case_id}",
    str(case_dir),
    f"case{case_id}",
  }
  related: list[str] = []
  for log_file in sorted(log_dir.glob(LOG_NAME_GLOB)):
    try:
      text = log_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
      continue
    if any(marker in text for marker in markers):
      related.append(str(log_file))
  return related


def normalize_attempts(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
  """提炼 manifest 中的自动修复记录。"""
  normalized: list[dict[str, Any]] = []
  for attempt in attempts:
    normalized.append(
      {
        "attempt": attempt.get("attempt"),
        "execution_outcome": attempt.get("execution_outcome"),
        "failure_category": attempt.get("failure_category"),
        "fix_summary": attempt.get("fix_summary"),
        "retry_recommended": attempt.get("retry_recommended"),
        "affected_repos": attempt.get("affected_repos") or [],
        "failure_summary_file": attempt.get("failure_summary_file"),
        "ai_result_file": attempt.get("ai_result_file"),
        "fix_report_file": attempt.get("fix_report_file"),
        "stop_reason": attempt.get("stop_reason"),
      }
    )
  return normalized


def parse_selected_cases(raw_cases: str | None) -> set[str]:
  """解析命令行传入的 case 过滤列表。"""
  if raw_cases is None:
    return set()
  return {
    case_id.strip()
    for case_id in raw_cases.split(",")
    if case_id.strip()
  }


def detect_final_prd_file(session_dir: Path) -> str | None:
  """定位 session 关联的最终 PRD 文件。"""
  final_prd_file = session_dir / "summary_effect" / "final_prd.md"
  if final_prd_file.is_file():
    return str(final_prd_file)
  return None


def detect_code_dir(project_root: Path) -> str | None:
  """定位默认代码目录。"""
  code_dir = project_root / "workdir"
  if code_dir.is_dir():
    return str(code_dir)
  return None


def detect_tech_design_dir(session_dir: Path) -> str | None:
  """定位 session 关联的技术方案目录。"""
  tech_design_dir = session_dir / "code"
  if tech_design_dir.is_dir():
    return str(tech_design_dir)
  return None


def collect_failed_cases(
  manifest: dict[str, Any],
  project_root: Path,
  session_dir: Path,
  selected_cases: set[str],
) -> dict[str, Any]:
  """从 manifest 中提取失败/异常 case 的聚合结果。"""
  cases = manifest.get("cases")
  if not isinstance(cases, list):
    raise ValueError("manifest.json 缺少 cases 数组")

  log_dir = session_dir / "cursor_agent_logs"
  failed_cases: list[dict[str, Any]] = []
  for item in cases:
    if not isinstance(item, dict):
      continue
    case_id = str(item.get("case_id", "")).strip()
    if selected_cases and case_id not in selected_cases:
      continue
    outcome = str(item.get("execution_outcome", "")).strip()
    if outcome not in FAIL_OUTCOMES:
      continue

    result_file = Path(str(item.get("result_file", ""))).expanduser()
    case_dir = result_file.parent if result_file.name else Path()
    failed_cases.append(
      {
        "case_id": case_id,
        "case_title": item.get("case_title"),
        "execution_outcome": outcome,
        "summary": item.get("summary"),
        "error_message": item.get("error_message"),
        "terminated_reason": item.get("terminated_reason"),
        "steps_file": item.get("steps_file"),
        "report_file": item.get("report_file"),
        "result_file": item.get("result_file"),
        "case_dir": str(case_dir),
        "logs_analysis_performed": item.get("logs_analysis_performed"),
        "attempts": normalize_attempts(item.get("attempts") or []),
        "attempt_artifacts": collect_attempt_files(case_dir),
        "related_cursor_logs": find_related_logs(
          log_dir=log_dir,
          case_id=case_id,
          case_dir=case_dir,
        ),
      }
    )

  return {
    "session_name": manifest.get("session_name"),
    "session_dir": str(session_dir),
    "manifest_file": str(session_dir / "e2e_case_execution" / "manifest.json"),
    "summary_file": manifest.get("summary_file"),
    "final_prd_file": detect_final_prd_file(session_dir),
    "code_dir": detect_code_dir(project_root),
    "tech_design_dir": detect_tech_design_dir(session_dir),
    "cursor_agent_log_dir": str(log_dir),
    "selected_cases": sorted(selected_cases),
    "failed_case_count": len(failed_cases),
    "failed_cases": failed_cases,
  }


def main() -> None:
  """执行聚合并输出 JSON。"""
  args = parse_args()
  project_root = Path(args.project_root).expanduser().resolve()
  session_dir = project_root / "runs" / args.session_name
  manifest_file = session_dir / "e2e_case_execution" / "manifest.json"

  if not manifest_file.is_file():
    raise FileNotFoundError(f"未找到 manifest.json: {manifest_file}")

  manifest = read_json(manifest_file)
  result = collect_failed_cases(
    manifest=manifest,
    project_root=project_root,
    session_dir=session_dir,
    selected_cases=parse_selected_cases(args.cases),
  )
  text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"

  if args.output:
    output = Path(args.output).expanduser().resolve()
    output.write_text(text, encoding="utf-8")
  print(text, end="")


if __name__ == "__main__":
  main()
