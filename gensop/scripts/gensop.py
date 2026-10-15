#!/usr/bin/env python3
"""Deterministic validation, preview, confirmation, and SOPower share export."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIB = 1024 * 1024
SOP_SHARE_KIND = "soper-sop-share"
SOP_SHARE_SCHEMA_VERSION = 2
WORKFLOW_VERSION = 1

REASON_MESSAGES = {
    "UNSAFE": "当前要求涉及无法安全规划的操作，不能生成 SOP。请调整操作方式或执行条件后再试。",
    "UNDEFINED": "当前目标的含义无法确定，不能生成 SOP。请说明该概念的含义或改用明确的目标后再试。",
    "IMPOSSIBLE": "当前目标或条件无法同时实现，不能生成 SOP。请调整目标或冲突条件后再试。",
    "DURATION": "当前时间要求无法与必要流程兼容，不能生成 SOP。请调整时间要求或任务范围后再试。",
    "TITLE_LENGTH": "当前标题要求无法在 40 个字符内表达，不能生成 SOP。请允许简化标题后再试。",
    "STEP_COUNT": "当前需求包含超过 8 个必须独立计时的阶段，不能生成单个 SOP。请缩小范围或拆分需求后再试。",
    "STEP_NAME_LENGTH": "当前步骤命名要求无法在每步 8 个字符内表达，不能生成 SOP。请允许简化名称或调整内容后再试。",
    "TAG_COUNT": "当前必要提示无法容纳在每步最多 3 个标签内，不能生成 SOP。请精简提示或调整任务范围后再试。",
    "TAG_LENGTH": "当前必要提示无法在每个标签 4 个字符内表达，不能生成 SOP。请允许简化提示后再试。",
    "GENERATION_FAILED": "本次未能生成符合要求的 SOP，请重新尝试。",
}
REASON_ORDER = list(REASON_MESSAGES)


class WorkflowError(Exception):
    pass


def codepoint_length(value: str) -> int:
    # Python 3's len() counts Unicode code points on supported builds.
    return len(value)


def is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"缺少 {missing}")
        if extra:
            details.append(f"多出 {extra}")
        raise WorkflowError(f"[响应契约] {path} 字段不精确：{'；'.join(details)}")


def require_record(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError(f"[响应契约] {path} 必须是对象")
    return value


def require_string(value: Any, path: str, maximum: int, layer: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"[{layer}] {path} 必须是去除首尾空白后非空的字符串")
    if codepoint_length(value) > maximum:
        raise WorkflowError(f"[{layer}] {path} 不得超过 {maximum} 个 Unicode 码点")
    return value


def validate_tags(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise WorkflowError(f"[SOPower 硬约束] {path} 必须是数组")
    if len(value) > 3:
        raise WorkflowError(f"[SOPower 硬约束] {path} 最多 3 个标签")
    for index, tag in enumerate(value):
        require_string(tag, f"{path}[{index}]", 4, "SOPower 硬约束")
    return value


def validate_duration(value: Any, path: str, enforce_generation: bool) -> int:
    if not is_integer(value) or value < 1 or value > 86400:
        raise WorkflowError(f"[SOPower 硬约束] {path} 必须是 1–86400 的整数秒")
    if enforce_generation and value < 60:
        raise WorkflowError(f"[GenSOP 生成要求] {path} 必须至少为 60 秒")
    return value


def validate_preview_step(value: Any, path: str) -> dict[str, Any]:
    step = require_record(value, path)
    exact_keys(step, {"name", "durationSeconds", "tags"}, path)
    name = require_string(step["name"], f"{path}.name", 60, "SOPower 硬约束")
    if codepoint_length(name) > 8:
        raise WorkflowError(f"[GenSOP 生成要求] {path}.name 不得超过 8 个 Unicode 码点")
    validate_duration(step["durationSeconds"], f"{path}.durationSeconds", True)
    validate_tags(step["tags"], f"{path}.tags")
    return step


def validate_sop_step(value: Any, path: str, enforce_generation: bool = True) -> dict[str, Any]:
    step = require_record(value, path)
    exact_keys(step, {"name", "duration", "tags"}, path)
    name = require_string(step["name"], f"{path}.name", 60, "SOPower 硬约束")
    if enforce_generation and codepoint_length(name) > 8:
        raise WorkflowError(f"[GenSOP 生成要求] {path}.name 不得超过 8 个 Unicode 码点")
    validate_duration(step["duration"], f"{path}.duration", enforce_generation)
    validate_tags(step["tags"], f"{path}.tags")
    return step


def validate_generate(response: dict[str, Any]) -> None:
    if response["reasons"] != []:
        raise WorkflowError("[响应契约] generate 的 reasons 必须是空数组")

    preview = require_record(response["preview"], "preview")
    exact_keys(preview, {"title", "steps", "totalDurationSeconds"}, "preview")
    title = require_string(preview["title"], "preview.title", 40, "SOPower 硬约束")
    if not isinstance(preview["steps"], list) or not 1 <= len(preview["steps"]) <= 8:
        raise WorkflowError("[GenSOP 生成要求] preview.steps 必须包含 1–8 个步骤")
    preview_steps = [
        validate_preview_step(step, f"preview.steps[{index}]")
        for index, step in enumerate(preview["steps"])
    ]
    total = preview["totalDurationSeconds"]
    if not is_integer(total):
        raise WorkflowError("[响应契约] preview.totalDurationSeconds 必须是整数")

    sop_data = require_record(response["sopData"], "sopData")
    exact_keys(sop_data, {"name", "steps"}, "sopData")
    require_string(sop_data["name"], "sopData.name", 40, "SOPower 硬约束")
    if not isinstance(sop_data["steps"], list) or not 1 <= len(sop_data["steps"]) <= 8:
        raise WorkflowError("[GenSOP 生成要求] sopData.steps 必须包含 1–8 个步骤")
    sop_steps = [
        validate_sop_step(step, f"sopData.steps[{index}]")
        for index, step in enumerate(sop_data["steps"])
    ]

    if title != sop_data["name"]:
        raise WorkflowError("[一致性] preview.title 与 sopData.name 必须完全相同")
    if len(preview_steps) != len(sop_steps):
        raise WorkflowError("[一致性] preview.steps 与 sopData.steps 数量不一致")
    for index, (shown, stored) in enumerate(zip(preview_steps, sop_steps)):
        if shown["name"] != stored["name"]:
            raise WorkflowError(f"[一致性] 第 {index + 1} 步名称不一致")
        if shown["durationSeconds"] != stored["duration"]:
            raise WorkflowError(f"[一致性] 第 {index + 1} 步时长不一致")
        if shown["tags"] != stored["tags"]:
            raise WorkflowError(f"[一致性] 第 {index + 1} 步标签不一致")
    calculated = sum(step["duration"] for step in sop_steps)
    if total != calculated:
        raise WorkflowError(
            f"[一致性] preview.totalDurationSeconds 应为 {calculated}，实际为 {total}"
        )


def validate_refuse(response: dict[str, Any]) -> None:
    if response["preview"] is not None or response["sopData"] is not None:
        raise WorkflowError("[响应契约] refuse 的 preview 与 sopData 必须为 null")
    reasons = response["reasons"]
    if not isinstance(reasons, list) or not reasons:
        raise WorkflowError("[响应契约] refuse 的 reasons 必须是非空数组")
    seen: set[str] = set()
    codes: list[str] = []
    for index, value in enumerate(reasons):
        reason = require_record(value, f"reasons[{index}]")
        exact_keys(reason, {"code", "message"}, f"reasons[{index}]")
        code = reason["code"]
        if code not in REASON_MESSAGES:
            raise WorkflowError(f"[响应契约] reasons[{index}].code 不在固定映射中")
        if code in seen:
            raise WorkflowError(f"[响应契约] 拒绝原因 {code} 重复")
        if reason["message"] != REASON_MESSAGES[code]:
            raise WorkflowError(f"[响应契约] {code} 必须逐字使用固定文案")
        seen.add(code)
        codes.append(code)
    if "GENERATION_FAILED" in seen and len(seen) != 1:
        raise WorkflowError("[响应契约] GENERATION_FAILED 必须单独返回")
    if codes != sorted(codes, key=REASON_ORDER.index):
        raise WorkflowError("[响应契约] 多个拒绝原因未按固定映射顺序返回")


def validate_response(value: Any) -> dict[str, Any]:
    response = require_record(value, "response")
    exact_keys(response, {"responseType", "reasons", "preview", "sopData"}, "response")
    response_type = response["responseType"]
    if response_type == "generate":
        if response["preview"] is None or response["sopData"] is None:
            raise WorkflowError("[响应契约] generate 必须同时包含 preview 与 sopData")
        validate_generate(response)
    elif response_type == "refuse":
        validate_refuse(response)
    else:
        raise WorkflowError('[响应契约] responseType 只能是 "generate" 或 "refuse"')
    return response


def validate_request(value: str) -> str:
    normalized = value.strip()
    length = codepoint_length(normalized)
    if length < 1 or length > 500:
        raise WorkflowError("[输入契约] 去除首尾空白后的需求必须为 1–500 个 Unicode 码点")
    return normalized


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"无法读取 {path}: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"[响应契约] {path} 不是有效 JSON: {exc.msg}") from exc


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def format_duration(seconds: int) -> str:
    hours, remaining = divmod(seconds, 3600)
    minutes, seconds = divmod(remaining, 60)
    parts = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if seconds or not parts:
        parts.append(f"{seconds}秒")
    return "".join(parts)


def render_result(response: dict[str, Any]) -> str:
    if response["responseType"] == "refuse":
        lines = ["# 无法生成 SOP", ""]
        lines.extend(f"- {reason['message']}" for reason in response["reasons"])
        return "\n".join(lines) + "\n"
    preview = response["preview"]
    lines = [
        f"# {preview['title']}",
        "",
        f"总时长：{format_duration(preview['totalDurationSeconds'])}（{preview['totalDurationSeconds']} 秒）",
        "",
        "| # | 步骤 | 时长 | 标签 |",
        "| ---: | --- | ---: | --- |",
    ]
    for index, step in enumerate(preview["steps"], start=1):
        tags = "、".join(step["tags"]) if step["tags"] else "—"
        lines.append(
            f"| {index} | {step['name']} | {format_duration(step['durationSeconds'])}（{step['durationSeconds']} 秒） | {tags} |"
        )
    return "\n".join(lines) + "\n"


def load_state(path: Path) -> dict[str, Any]:
    state = require_record(read_json(path), "state")
    exact_keys(
        state,
        {
            "workflowVersion",
            "status",
            "request",
            "response",
            "confirmedResponse",
            "preparedAt",
            "confirmedAt",
        },
        "state",
    )
    if state["workflowVersion"] != WORKFLOW_VERSION:
        raise WorkflowError("工作状态版本不受支持")
    validate_request(state["request"])
    validate_response(state["response"])
    return state


def prepare(request_path: Path, response_path: Path, state_path: Path, preview_path: Path) -> None:
    request = validate_request(read_text(request_path))
    response = validate_response(read_json(response_path))
    status = "awaiting_confirmation" if response["responseType"] == "generate" else "refused"
    state = {
        "workflowVersion": WORKFLOW_VERSION,
        "status": status,
        "request": request,
        "response": response,
        "confirmedResponse": None,
        "preparedAt": int(time.time() * 1000),
        "confirmedAt": None,
    }
    write_json(state_path, state)
    rendered = render_result(response)
    atomic_write_text(preview_path, rendered)
    sys.stdout.write(rendered)
    if status == "refused":
        sys.stdout.write("\n拒绝响应已记录；不得确认或导出。\n")
    else:
        sys.stdout.write("\n状态：等待用户明确确认；当前不可导出。\n")


def confirm(state_path: Path) -> None:
    state = load_state(state_path)
    if state["status"] != "awaiting_confirmation":
        raise WorkflowError("只有已通过校验并等待确认的 generate 结果可以确认")
    if state["response"]["responseType"] != "generate":
        raise WorkflowError("拒绝响应不能确认")
    state["confirmedResponse"] = copy.deepcopy(state["response"])
    state["confirmedAt"] = int(time.time() * 1000)
    state["status"] = "confirmed"
    write_json(state_path, state)
    print("已锁定用户确认时的预览快照；现在可以导出。")


def validate_envelope(value: Any) -> None:
    envelope = require_record(value, "envelope")
    exact_keys(envelope, {"kind", "schemaVersion", "exportedAt", "payload"}, "envelope")
    if envelope["kind"] != SOP_SHARE_KIND or envelope["schemaVersion"] != SOP_SHARE_SCHEMA_VERSION:
        raise WorkflowError("[SOPower 硬约束] envelope 类型或版本错误")
    if not is_integer(envelope["exportedAt"]) or envelope["exportedAt"] < 0:
        raise WorkflowError("[SOPower 硬约束] exportedAt 必须是非负整数毫秒时间戳")
    payload = require_record(envelope["payload"], "payload")
    exact_keys(payload, {"name", "steps"}, "payload")
    require_string(payload["name"], "payload.name", 40, "SOPower 硬约束")
    if not isinstance(payload["steps"], list) or len(payload["steps"]) > 8:
        raise WorkflowError("[SOPower 硬约束] payload.steps 最多 8 个步骤")
    for index, step in enumerate(payload["steps"]):
        validate_sop_step(step, f"payload.steps[{index}]", enforce_generation=False)


def safe_export_path(output_dir: Path, now: datetime) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"SOP-share-{stamp}"
    candidate = output_dir / f"{base}.sop.json"
    suffix = 2
    while candidate.exists():
        candidate = output_dir / f"{base}-{suffix:02d}.sop.json"
        suffix += 1
    return candidate


def export_share(state_path: Path, output_dir: Path) -> Path:
    state = load_state(state_path)
    if state["status"] != "confirmed" or state["confirmedResponse"] is None:
        raise WorkflowError("尚未取得用户明确确认，不能导出")
    confirmed = validate_response(state["confirmedResponse"])
    if confirmed["responseType"] != "generate":
        raise WorkflowError("拒绝响应不能导出")
    if state["response"] != confirmed:
        raise WorkflowError("当前内容与用户确认的预览不一致；请重新校验并确认")
    sop_data = confirmed["sopData"]
    envelope = {
        "kind": SOP_SHARE_KIND,
        "schemaVersion": SOP_SHARE_SCHEMA_VERSION,
        "exportedAt": int(time.time() * 1000),
        "payload": copy.deepcopy(sop_data),
    }
    validate_envelope(envelope)
    content = json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"
    byte_count = len(content.encode("utf-8"))
    if byte_count > MIB:
        raise WorkflowError(f"[SOPower 硬约束] 导出文件为 {byte_count} 字节，超过 1 MiB")
    path = safe_export_path(output_dir, datetime.now(timezone.utc))
    # Exclusive creation is the final guard against overwriting a concurrent export.
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise WorkflowError(f"导出目标已存在，未覆盖：{path}") from exc
    print(path.resolve())
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="校验模型响应并生成预览和待确认状态")
    prepare_parser.add_argument("--request", type=Path, required=True)
    prepare_parser.add_argument("--response", type=Path, required=True)
    prepare_parser.add_argument("--state", type=Path, required=True)
    prepare_parser.add_argument("--preview", type=Path, required=True)

    confirm_parser = subparsers.add_parser("confirm", help="仅在用户明确确认后锁定当前预览")
    confirm_parser.add_argument("--state", type=Path, required=True)

    export_parser = subparsers.add_parser("export", help="导出用户已确认的 SOPower Share 文件")
    export_parser.add_argument("--state", type=Path, required=True)
    export_parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(args.request, args.response, args.state, args.preview)
        elif args.command == "confirm":
            confirm(args.state)
        elif args.command == "export":
            export_share(args.state, args.output_dir)
        return 0
    except WorkflowError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
