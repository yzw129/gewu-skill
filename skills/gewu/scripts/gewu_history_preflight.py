#!/usr/bin/env python3
"""Strict pre-freeze archival check for Gewu's ten genuine historical tasks.

Verifies original/revised file existence, byte hashes, Office ZIP CRC or PDF
signature, and availability of exact prompt provenance. This checks neither
the scientific correctness of revisions nor the independence of reviewers.
Run locally: do not upload user documents, file IDs, or private registry to GitHub.
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


def digest_file(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def evaluate(registry, strict=False):
    tasks = registry.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 10:
        raise ValueError("真实回放预检要求恰好十个历史任务")
    ids = set()
    outcomes = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("历史任务项格式错误")
        tid = task.get("task_id")
        if not isinstance(tid, str) or not tid or tid in ids:
            raise ValueError("缺失或重复的历史任务 ID")
        ids.add(tid)
        reasons = []
        files_checked = 0
        for part in ("historical_inputs", "historical_outputs"):
            artifacts = task.get(part)
            if not isinstance(artifacts, list) or not artifacts:
                reasons.append(part + " 缺少真实工件")
                continue
            for item in artifacts:
                if not isinstance(item, dict):
                    reasons.append("工件格式错误")
                    continue
                path = Path(item.get("local_path") or "/nonexistent-gewu-historical-asset")
                if not path.is_file():
                    reasons.append("工件不存在: " + str(path))
                    continue
                expected = item.get("sha256")
                if not expected or digest_file(path) != expected:
                    reasons.append("工件字节指纹不匹配: " + path.name)
                    continue
                if path.suffix.lower() in (".docx", ".xlsx", ".pptx"):
                    try:
                        with zipfile.ZipFile(path) as f:
                            if f.testzip() is not None:
                                reasons.append("Office CRC 错误: " + path.name)
                                continue
                    except (OSError, zipfile.BadZipFile):
                        reasons.append("Office 文件损坏: " + path.name)
                        continue
                elif path.suffix.lower() == ".pdf":
                    with path.open("rb") as f:
                        if f.read(5) != b"%PDF-":
                            reasons.append("PDF 文件头错误: " + path.name)
                            continue
                files_checked += 1
        original = task.get("original_prompt_transcript")
        if not isinstance(original, str) or original in ("", "not_recovered", "missing"):
            reasons.append("缺少逐字原始任务指令")
        if not task.get("prompt_source_ref"):
            reasons.append("缺少原始指令的来源定位")
        outcomes.append({
            "task_id": tid, "file_count_verified": files_checked,
            "strict_history_eligible": len(reasons) == 0,
            "blocking_reasons": reasons
        })
    result = {
        "schema_version": "0.4-exp-history-preflight",
        "task_count": len(tasks),
        "verified_file_count": sum(x["file_count_verified"] for x in outcomes),
        "fully_replayable_count": sum(x["strict_history_eligible"] for x in outcomes),
        "can_claim_real_success_gain": False,
        "note": "文件哈希和来源定位核查不是科研能力效果验证；无外部 A/B 结果",
        "tasks": outcomes
    }
    return result, (2 if strict and result["fully_replayable_count"] < 10 else 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit ten real historical research task traces")
    parser.add_argument("registry")
    parser.add_argument("--strict", action="store_true",
                        help="Only exit successfully when all ten are genuinely replayable")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        content = json.loads(Path(args.registry).read_text(encoding="utf8"))
        result, status = evaluate(content, args.strict)
        print(json.dumps({
            "task_count": result["task_count"],
            "verified_file_count": result["verified_file_count"],
            "fully_replayable_count": result["fully_replayable_count"],
            "can_claim_real_success_gain": False
        }, ensure_ascii=False, indent=2))
        if args.output:
            path = Path(args.output)
            if path.exists():
                raise ValueError("已有审计结果不可覆盖，请使用新文件路径")
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        return status
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        print("错误：" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
