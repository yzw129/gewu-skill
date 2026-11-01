#!/usr/bin/env python3
"""Gewu capability distillation v0.5: domain-neutral review gates, skill compilation.

This is a workflow compiler and consistency checker, NOT model training, a source
harvester, a manuscript writer, a plotting engine, or an automatic quality judge.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DOMAINS = {
    "research": {
        "title": "科研推理",
        "description": "科学问题、可辨识性、假设、对照实验、证据边界",
        "metrics": ["evidence_validity", "hypothesis_testability", "design_validity", "counterexample_handling"],
        "checks": [
            "先明确目标量、实验单位、可观测变量及潜在混杂",
            "提出可证伪假设、竞争解释与失败判据",
            "固定训练/验证/测试划分、基线、消融及评价指标",
            "分开记录文献事实、推导、假设和实际验证"
        ]
    },
    "writing": {
        "title": "学术写作",
        "description": "论证结构、结果写作、引文核验、修订与语言清晰度",
        "metrics": ["claim_fidelity", "argument_coherence", "citation_accuracy", "writing_clarity"],
        "checks": [
            "先组织结论和证据，再写段落；一句一意，避免无依据的断言",
            "逐条核查数值、公式、统计结果与数据来源；缺证据必须标记",
            "核查方法与结果一致、图表与正文一致、引言缺口与实际贡献一致",
            "保存写作前后版本及修改理由，不把文风模仿当作科研事实"
        ]
    },
    "visualization": {
        "title": "科学绘图",
        "description": "数据图表、机制示意图、数据忠实度、布局及导出",
        "metrics": ["data_fidelity", "semantic_correctness", "readability", "reproducibility"],
        "checks": [
            "先判断输出是定量数据图还是机制示意图，选择合适的表现形式",
            "数据图保留数据来源、单位、刻度、归一化与不确定性；禁止改变数值含义",
            "机制图核查方框、关系、箭头方向与数学符号；不可用视觉美感替代科学正确性",
            "检查字体、配色、对齐、图注、可访问性、格式和导出尺寸",
            "有代码的图保留可复现脚本与数据指纹；生成位图不等于可编辑矢量图"
        ]
    },
    "presentation": {
        "title": "学术汇报",
        "description": "报告叙事、内容压缩、PPT结构、图文组合及可编辑性",
        "metrics": ["claim_fidelity", "narrative_clarity", "visual_hierarchy", "editability"],
        "checks": [
            "按对象与时间限制确定报告目标、核心结论和章节",
            "每页只承载一个主要信息，保证研究结果和来源无遗漏与歪曲",
            "检查字号、布局、阅读顺序、图表可见性和演示环境",
            "若要求可编辑PPT，检查文字与主要图形能否独立修改，而非只导出整页图片"
        ]
    }
}

REVIEW_STATES = {"candidate", "reviewed", "tested"}
SOURCE_KINDS = {"paper", "skill", "guideline", "code", "worked_example", "failure_record"}
FIELDS = ("trigger", "action", "why", "exceptions", "verification")
MARKER = "[UNVERIFIED CANDIDATE]"


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"读取 JSON 失败 {path}: {exc}") from exc


def write(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def require_new(path):
    if Path(path).exists():
        raise ValueError(f"文件/目录已存在，拒绝覆盖：{path}")


def default_record(name, domain):
    return {
        "schema_version": "0.5",
        "capability_id": name,
        "domain": domain,
        "purpose": DOMAINS[domain]["description"],
        "target_output": "实际使用该能力时要求生成的具体研究/写作/图形/汇报成果",
        "sources": [],
        "rules": [],
        "limitations": ["尚未采集和核查来源，不能声称已习得任何能力"]
    }


def default_evaluation(domain):
    return {
        "schema_version": "0.5",
        "domain": domain,
        "rubric": list(DOMAINS[domain]["metrics"]),
        "scenarios": [
            {"id": "replace-dev", "split": "dev", "prompt": "替换为真实开发任务",
             "source_ids": [], "asset_checks": []},
            {"id": "replace-test", "split": "test", "prompt": "替换为未见过的独立测试任务",
             "source_ids": [], "asset_checks": []}
        ],
        "scoring_policy": "先记录定量检查结果，再由至少一名人工评分人独立核查；不可自动声明已达到质量要求"
    }


def validate(root, require_reviewed=False):
    root = Path(root)
    record = read(root / "capability.json")
    evaluation = read(root / "evaluation.json")
    errors, warnings = [], []
    domain = record.get("domain")
    if record.get("schema_version") != "0.5" or domain not in DOMAINS:
        errors.append("未知能力版本或领域；必须为 v0.5 的有效模块")
        return errors, warnings, record, evaluation
    if record.get("capability_id") in (None, "") or not re.fullmatch(
        r"[a-z][a-z0-9-]{1,63}", str(record.get("capability_id", ""))):
        errors.append("capability_id 应为小写横线连接 ID，长度 2-64")
    for k in ("purpose", "target_output"):
        if not isinstance(record.get(k), str) or not record[k].strip():
            errors.append(f"{k} 不能为空")
    sources = record.get("sources")
    if not isinstance(sources, list):
        errors.append("sources 必须为数组")
        sources = []
    source_map = {}
    for idx, item in enumerate(sources):
        if not isinstance(item, dict):
            errors.append(f"sources[{idx}] 不是对象")
            continue
        sid = item.get("id")
        if not isinstance(sid, str) or not sid or sid in source_map:
            errors.append(f"sources[{idx}] 来源 ID 缺失或重复")
            continue
        source_map[sid] = item
        if item.get("kind") not in SOURCE_KINDS:
            errors.append(f"{sid} 来源类型无效")
        if not all(isinstance(item.get(k), str) and item[k].strip()
                   for k in ("title", "location", "locator")):
            errors.append(f"{sid} 必须记录来源题名、位置、具体定位")
        if type(item.get("reviewed")) is not bool:
            errors.append(f"{sid} reviewed 必须为布尔值")
        if not isinstance(item.get("usage_rights"), str) or not item["usage_rights"].strip():
            errors.append(f"{sid} 须说明合法使用和引用/许可情况")
    rules = record.get("rules")
    if not isinstance(rules, list):
        errors.append("rules 必须为数组")
        rules = []
    ids, approved = set(), 0
    used_sources = set()
    for idx, r in enumerate(rules):
        where = f"rules[{idx}]"
        if not isinstance(r, dict):
            errors.append(f"{where} 不是对象")
            continue
        rid = r.get("id")
        if not isinstance(rid, str) or not rid or rid in ids:
            errors.append(f"{where} 规则 ID 缺失或重复")
        else:
            ids.add(rid)
        if r.get("status") not in REVIEW_STATES:
            errors.append(f"{where}.status 不合法")
        for k in FIELDS:
            if not isinstance(r.get(k), str) or not r[k].strip():
                errors.append(f"{where}.{k} 不能为空")
        references = r.get("source_ids")
        if not isinstance(references, list) or not references:
            errors.append(f"{where} 没有来源引用")
            continue
        if len(set(references)) != len(references):
            errors.append(f"{where} 存在重复来源引用")
        for sid in references:
            used_sources.add(sid)
            if sid not in source_map:
                errors.append(f"{where} 引用了未知来源 {sid}")
            elif r.get("status") in ("reviewed", "tested") and not source_map[sid].get("reviewed"):
                errors.append(f"{where} 审查规则引用了未审查来源 {sid}")
        if r.get("status") in ("reviewed", "tested"):
            approved += 1
    if not rules:
        warnings.append("没有任何能力规则；尚未完成蒸馏")
    if approved == 0:
        warnings.append("没有已审查规则；不能生成正式 Skill")
    if any(sid not in source_map for sid in used_sources):
        warnings.append("存在悬空引用；请检查来源表")
    if evaluation.get("schema_version") != "0.5" or evaluation.get("domain") != domain:
        errors.append("evaluation 与能力版本或领域不一致")
    if evaluation.get("rubric") != DOMAINS[domain]["metrics"]:
        errors.append("评价维度必须与能力领域固定量表一致")
    scenarios = evaluation.get("scenarios")
    if not isinstance(scenarios, list):
        errors.append("scenarios 必须为数组")
        scenarios = []
    test_sets, test_ids = set(), set()
    for i, t in enumerate(scenarios):
        if not isinstance(t, dict):
            errors.append("任务不是对象")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid or tid in test_ids:
            errors.append(f"scenarios[{i}].id 缺失或重复")
        else:
            test_ids.add(tid)
        split = t.get("split")
        if split not in ("dev", "test"):
            errors.append(f"scenarios[{i}].split 必须为 dev 或 test")
        else:
            test_sets.add(split)
        if not isinstance(t.get("prompt"), str) or not t["prompt"].strip():
            errors.append(f"scenarios[{i}].prompt 不能为空")
        elif "替换为" in t["prompt"]:
            warnings.append(f"{tid}: 评估问题仍为占位符，不能冻结")
        ids_in_task = t.get("source_ids")
        if not isinstance(ids_in_task, list):
            errors.append(f"{tid}: source_ids 必须为数组")
            continue
        # Any held-out input used for learning invalidates the independent test.
        if split == "test" and set(ids_in_task) & used_sources:
            errors.append(f"{tid}: 独立测试来源已用于规则蒸馏（泄漏）")
        if not isinstance(t.get("asset_checks"), list):
            errors.append(f"{tid}: asset_checks 必须为数组")
    if test_sets != {"dev", "test"}:
        errors.append("必须同时有开发集和独立测试集")
    lock = root / "evaluation.lock.json"
    if lock.exists():
        if read(lock).get("sha256") != fingerprint(evaluation):
            errors.append("评价计划已冻结，但其内容被修改")
    elif require_reviewed:
        errors.append("正式编译前必须冻结评估计划")
    else:
        warnings.append("评价计划尚未冻结")
    if require_reviewed and approved == 0:
        errors.append("没有通过来源审查的能力规则")
    return errors, warnings, record, evaluation


def cmd_init(args):
    root = Path(args.directory)
    require_new(root)
    if args.domain not in DOMAINS:
        raise ValueError("未知领域")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", args.id):
        raise ValueError("能力 ID 必须是小写字母开头的横线连接格式")
    root.mkdir(parents=True)
    write(root / "capability.json", default_record(args.id, args.domain))
    write(root / "evaluation.json", default_evaluation(args.domain))
    print(f"已创建 {args.domain} 能力项目：{root}；空白模板不代表已经蒸馏")
    return 0


def cmd_check(args):
    errors, warnings, record, _ = validate(args.directory)
    print(f"能力：{record.get('capability_id')}；结构错误 {len(errors)}，提醒 {len(warnings)}")
    for item in errors:
        print("ERROR", item)
    for item in warnings:
        print("WARN ", item)
    if not errors:
        print("PASS: 仅字段和引用一致性；并非来源真实性或能力效果验证")
    return int(bool(errors))


def cmd_freeze(args):
    root = Path(args.directory)
    errors, warnings, _, evaluation = validate(root)
    if errors:
        raise ValueError("检查未通过：" + "; ".join(errors[:5]))
    if any("占位符" in x for x in warnings):
        raise ValueError("请先替换开发集和测试集的占位任务")
    lock = root / "evaluation.lock.json"
    require_new(lock)
    write(lock, {"schema_version": "0.5", "sha256": fingerprint(evaluation),
                 "timestamp": datetime.now(timezone.utc).isoformat(),
                 "note": "测试集不得参与蒸馏或版本选择"})
    print(f"已冻结能力评价：{lock}")
    return 0


def compile_skill(record, review_only=True):
    domain = record["domain"]
    spec = DOMAINS[domain]
    rules = [r for r in record["rules"] if not review_only or r["status"] in ("reviewed", "tested")]
    status = "PROVISIONAL: 审查规则的执行协议，尚未证明能力提升" if review_only else "DRAFT: 候选规则未经完整核查"
    lines = [
        "---", "name: gewu-" + record["capability_id"],
        "description: " + spec["title"] + "方向的条件性执行能力；使用时先核查证据、输入、限制和独立评估",
        "---", "", "# " + spec["title"] + " · Gewu 能力 Skill",
        "", "> " + status, "",
        "## 工作目标", "", record["purpose"], "", "目标产物：" + record["target_output"], "",
        "## 领域内置检查", ""
    ]
    lines += ["- " + item for item in spec["checks"]]
    lines += ["", "## 条件性能力规则", ""]
    for r in rules:
        lines += [f"### {r['id']}",
                  f"- IF：{r['trigger']}", f"- THEN：{r['action']}",
                  f"- BECAUSE：{r['why']}", f"- EXCEPT：{r['exceptions']}",
                  f"- CHECK：{r['verification']}",
                  "- SOURCE IDs：" + ", ".join(r["source_ids"]),
                  "- 核验级别：" + r["status"], ""]
    lines += ["## 执行边界", "",
              "- 不得把外部 Skill 的大段指令或他人图像/论文内容直接复制为自己的作品。",
              "- 必须区分实际渲染、静态检查、人工审查、独立测试；不能以美观或语感替代正确性。",
              "- 不重新训练基础模型参数，能力增益须经独立未见任务的同条件比较验证。",
              "- 不得将 test 集答案或评价反馈用于当前轮 Skill 的蒸馏或修订。", ""]
    return "\n".join(lines)


def cmd_compile(args):
    root = Path(args.directory)
    errors, _, record, _ = validate(root, require_reviewed=not args.preview)
    if errors:
        raise ValueError("能力审查未通过：" + "; ".join(errors[:10]))
    if not record["rules"]:
        raise ValueError("没有可编译的能力规则")
    output = Path(args.output)
    require_new(output)
    output.mkdir(parents=True)
    skill = compile_skill(record, review_only=not args.preview)
    (output / "SKILL.md").write_text(skill, encoding="utf-8")
    write(output / "manifest.json", {
        "schema_version": "0.5", "domain": record["domain"],
        "source_record_sha256": fingerprint(record),
        "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
        "review_status": "reviewed_rules_not_behaviorally_tested" if not args.preview else "unreviewed_draft",
        "note": "脚本不验证他人 Skill 的许可、不运行模型训练或对输出作主观自动评分"
    })
    print(f"生成 {output / 'SKILL.md'}：{'草稿' if args.preview else '审查版'}，不代表实际能力已提升")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Gewu v0.5 ability distillation registry")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("init")
    a.add_argument("directory"); a.add_argument("--id", required=True)
    a.add_argument("--domain", choices=tuple(DOMAINS), required=True)
    a.set_defaults(fn=cmd_init)
    for name, func in (("check", cmd_check), ("freeze", cmd_freeze)):
        a = sub.add_parser(name); a.add_argument("directory"); a.set_defaults(fn=func)
    a = sub.add_parser("compile"); a.add_argument("directory")
    a.add_argument("--output", required=True); a.add_argument("--preview", action="store_true")
    a.set_defaults(fn=cmd_compile)
    opts = p.parse_args(argv)
    try:
        return opts.fn(opts)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
