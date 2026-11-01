#!/usr/bin/env python3
"""Import historically distilled rule cards as UNVERIFIED Gewu experiences.

This script is intentionally a one-way candidate-only import: it never marks
experiences verified, makes external review claims, or uses holdout tasks for
learning. Source documents should remain in private local workspaces.
"""
import argparse
import json
import sys
from pathlib import Path


def import_cards(payload, excluded_task_ids=()):
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("缺少候选规则")
    excluded = set(excluded_task_ids)
    seen, experiences = set(), []
    for rule in rules:
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid or rid in seen:
            raise ValueError("规则 ID 缺失或重复")
        seen.add(rid)
        if rule.get("status") != "candidate" or rule.get("success_outcome") != "not_verified":
            raise ValueError(f"{rid}: 非候选状态，拒绝自动转换")
        for field in ("trigger", "action", "rationale", "limits",
                      "verification_check", "domain"):
            value = rule.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{rid}: 缺少 {field}")
        origins = rule.get("source_task_ids")
        if (not isinstance(origins, list) or not origins or
                any(not isinstance(x, str) or not x for x in origins) or
                len(origins) != len(set(origins))):
            raise ValueError(f"{rid}: 来源任务ID错误")
        if set(origins) & excluded:
            raise ValueError(f"{rid}: 经验来源与测试/留出任务泄漏")
        experiences.append({
            "id": rid, "status": "candidate", "tags": [rule["domain"]],
            "trigger": rule["trigger"], "action": rule["action"],
            "reason": rule["rationale"], "limits": rule["limits"],
            "verification_check": rule["verification_check"],
            "source_task_ids": origins,
            "verification": {
                "verdict": "pending", "reviewer_id": None, "verified_at": None,
                "evidence_ref": "PRIVATE_EVIDENCE_REVIEW_REQUIRED"
            },
            "import_note": "原稿—修订稿仅支持候选规则；不能自动升级为 verified"
        })
    return {"schema_version": "0.4-exp1", "experiences": experiences}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gewu historical cards -> candidate experience store")
    parser.add_argument("--cards", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--excluded-task-ids", default="",
                        help="Comma-separated held-out task IDs")
    args = parser.parse_args(argv)
    target = Path(args.output)
    if target.exists():
        raise ValueError("拒绝覆盖已有经验库")
    cards = json.loads(Path(args.cards).read_text(encoding="utf8"))
    blocked = [x.strip() for x in args.excluded_task_ids.split(",") if x.strip()]
    result = import_cards(cards, blocked)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(f"已写入 {len(result['experiences'])} 条候选经验：无一项标为 verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
