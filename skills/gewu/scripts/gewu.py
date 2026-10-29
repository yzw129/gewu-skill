#!/usr/bin/env python3
"""GEWU Research Edition: local scaffolding, structural audits, and rule compilation.

No network requests, LLM calls, semantic review, or scientific validation are performed.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
TEMPLATES = SKILL_ROOT / 'templates'
ACCESS_LEVELS = {'metadata': 0, 'abstract': 1, 'fulltext': 2}
PART_LEVELS = {'metadata': 0, 'abstract': 1, 'introduction': 2, 'methods': 2,
               'results': 2, 'discussion': 2, 'conclusion': 2, 'supplementary': 2, 'other': 2, 'references': 2}
KINDS = {'fact', 'interpretation', 'hypothesis', 'recommendation'}
STATUSES = {'candidate', 'reviewed', 'tested'}
SEARCH_STATUSES = {'not_started', 'searched', 'not_applicable'}


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load(path, errors):
    if not path.is_file():
        errors.append(f'缺少文件: {path.name}')
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        errors.append(f'无法读取 {path.name}: {e}')
        return None


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def meaningful(v):
    return isinstance(v, str) and bool(v.strip())


def normalized_doi(doi):
    return re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi.strip().lower())


def fingerprint(block):
    payload = {k: v for k, v in block.items() if k not in ('frozen', 'frozen_at', 'fingerprint')}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def audit(directory):
    d = Path(directory)
    errors, warnings = [], []
    project = load(d / 'project.json', errors)
    papers = load(d / 'papers.json', errors)
    rules = load(d / 'rules.json', errors)
    if not isinstance(project, dict):
        errors.append('project.json 必须是对象')
        project = {}
    if project.get('schema_version') != '0.2':
        errors.append('project.schema_version 必须是 "0.2"')
    for field in ('project_id', 'topic', 'scope', 'objective'):
        if not meaningful(project.get(field)):
            errors.append(f'project.{field} 必须是非空字符串')
    protocol = project.get('protocol')
    evaluation = project.get('evaluation')
    if not isinstance(protocol, dict):
        errors.append('project.protocol 必须是对象')
        protocol = {}
    if not isinstance(evaluation, dict):
        errors.append('project.evaluation 必须是对象')
        evaluation = {}
    for label, item in (('protocol', protocol), ('evaluation', evaluation)):
        if not isinstance(item.get('frozen'), bool):
            errors.append(f'project.{label}.frozen 必须为布尔值')
        elif item['frozen']:
            if item.get('fingerprint') != fingerprint(item):
                errors.append(f'project.{label} 已冻结配置被更改或缺少指纹')
        else:
            warnings.append(f'{label} 未冻结；归纳前必须固定相应协议')
    for field in ('sources', 'queries', 'inclusion', 'exclusion'):
        if not isinstance(protocol.get(field), list):
            errors.append(f'project.protocol.{field} 必须是数组')
    holdout = evaluation.get('holdout_ids', [])
    if not isinstance(holdout, list) or any(not meaningful(x) for x in holdout):
        errors.append('project.evaluation.holdout_ids 必须是非空 ID 构成的数组（允许空数组）')
        holdout = []
    if len(set(holdout)) != len(holdout):
        errors.append('holdout_ids 存在重复')
    if not isinstance(papers, list):
        errors.append('papers.json 必须是数组')
        papers = []
    if not isinstance(rules, list):
        errors.append('rules.json 必须是数组')
        rules = []
    paper_map, doi_map = {}, {}
    for i, paper in enumerate(papers):
        name = f'papers[{i}]'
        if not isinstance(paper, dict):
            errors.append(f'{name} 必须是对象')
            continue
        pid = paper.get('paper_id')
        if not meaningful(pid):
            errors.append(f'{name}.paper_id 不能为空')
        elif pid in paper_map:
            errors.append(f'{name}: 重复 paper_id {pid}')
        else:
            paper_map[pid] = paper
        if not meaningful(paper.get('title')):
            errors.append(f'{name}.title 不能为空')
        if paper.get('access_level') not in ACCESS_LEVELS:
            errors.append(f'{name}.access_level 应为 metadata/abstract/fulltext')
        if paper.get('pool') not in ('synthesis', 'holdout'):
            errors.append(f'{name}.pool 应为 synthesis/holdout')
        screening = paper.get('screening')
        if not isinstance(screening, dict) or screening.get('decision') not in ('pending', 'included', 'excluded'):
            errors.append(f'{name}.screening.decision 非法')
        if not paper.get('doi') and not paper.get('url'):
            warnings.append(f'{name}: 无 DOI/URL，需要人工核验来源')
        doi = paper.get('doi')
        if doi:
            if not isinstance(doi, str):
                errors.append(f'{name}.doi 必须为字符串或 null')
            else:
                doi = normalized_doi(doi)
                if not doi.startswith('10.') or '/' not in doi:
                    warnings.append(f'{name}.doi 格式可疑（不代表在线核实）')
                if doi in doi_map:
                    errors.append(f'{name}: 重复 DOI {doi}，与 {doi_map[doi]} 冲突')
                doi_map[doi] = pid
    for pid in holdout:
        if pid not in paper_map:
            errors.append(f'holdout_id {pid} 不在 papers.json')
        elif paper_map[pid].get('pool') != 'holdout':
            errors.append(f'holdout_id {pid} 在 papers.json 未标注 pool=holdout')
    for pid, p in paper_map.items():
        if p.get('pool') == 'holdout' and pid not in holdout:
            errors.append(f'paper {pid} 为 holdout，但不在 evaluation.holdout_ids')
    rule_ids = set()
    for i, rule in enumerate(rules):
        name = f'rules[{i}]'
        if not isinstance(rule, dict):
            errors.append(f'{name} 必须是对象')
            continue
        rid = rule.get('rule_id')
        if not meaningful(rid):
            errors.append(f'{name}.rule_id 不能为空')
        elif rid in rule_ids:
            errors.append(f'{name}: 重复 rule_id {rid}')
        else:
            rule_ids.add(rid)
        for field in ('question', 'statement', 'condition', 'action', 'rationale', 'limits'):
            if not meaningful(rule.get(field)):
                errors.append(f'{name}.{field} 必须是非空字符串')
        if rule.get('kind') not in KINDS:
            errors.append(f'{name}.kind 非法')
        if rule.get('status') not in STATUSES:
            errors.append(f'{name}.status 非法')
        is_reviewed = rule.get('status') in ('reviewed', 'tested')
        evidence = rule.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            errors.append(f'{name}.evidence 至少一条')
            evidence = []
        counter = rule.get('counterexamples')
        if not isinstance(counter, list):
            errors.append(f'{name}.counterexamples 必须是数组')
            counter = []
        search = rule.get('counterexample_search')
        if not isinstance(search, dict) or search.get('status') not in SEARCH_STATUSES:
            errors.append(f'{name}.counterexample_search.status 非法')
        elif is_reviewed and search['status'] == 'not_started':
            errors.append(f'{name}: reviewed 规则尚未开展反例检索')
        if is_reviewed and not evaluation.get('frozen'):
            errors.append(f'{name}: reviewed 规则要求先冻结 evaluation 留出集')
        supported_by = set()
        for label, items in (('evidence', evidence), ('counterexamples', counter)):
            for j, item in enumerate(items):
                where = f'{name}.{label}[{j}]'
                if not isinstance(item, dict):
                    errors.append(f'{where} 必须是对象')
                    continue
                pid = item.get('paper_id')
                paper = paper_map.get(pid)
                if paper is None:
                    errors.append(f'{where}: 引用了不存在的 paper_id {pid!r}')
                else:
                    supported_by.add(pid)
                    if paper.get('pool') == 'holdout':
                        errors.append(f'{where}: 禁止把留出论文 {pid} 用于规则归纳')
                    if (paper.get('screening') if isinstance(paper.get('screening'), dict) else {}).get('decision') != 'included':
                        errors.append(f'{where}: 论文 {pid} 尚未纳入综合集')
                    source_part = item.get('source_part')
                    if source_part not in PART_LEVELS:
                        errors.append(f'{where}.source_part 非法')
                    elif paper.get('access_level') in ACCESS_LEVELS and \
                            ACCESS_LEVELS[paper['access_level']] < PART_LEVELS[source_part]:
                        errors.append(f'{where}: 证据来源层级超出论文实际阅读范围')
                for field in ('locator', 'summary'):
                    if not meaningful(item.get(field)):
                        errors.append(f'{where}.{field} 必须是非空字符串')
                if item.get('review_status') not in ('unchecked', 'checked'):
                    errors.append(f'{where}.review_status 非法')
                if is_reviewed and item.get('review_status') != 'checked':
                    errors.append(f'{where}: reviewed/tested 规则必须逐项人工核对证据')
        if len(supported_by) == 1:
            warnings.append(f'{name}: 目前只有单篇来源；不能称为领域共识')
        if rule.get('status') == 'tested':
            warnings.append(f'{name}: tested 状态须另附独立评估记录；此工具不核验其真实性')
    if not papers:
        warnings.append('没有论文记录：尚未开展文献分析')
    if not rules:
        warnings.append('没有蒸馏规则：尚未形成科研方法 Skill')
    if not holdout:
        warnings.append('留出论文集合为空：无法评估跨论文泛化')
    return errors, warnings, project, papers, rules


def print_audit(directory):
    errors, warnings, _, _, _ = audit(directory)
    print(f'GEWU v0.3 结构检查：{len(errors)} 错误，{len(warnings)} 提醒')
    for e in errors:
        print('ERROR', e)
    for w in warnings:
        print('WARN ', w)
    if not errors:
        print('PASS: 仅结构与引用关系通过；不代表科研结论或 DOI 已实际核验。')
    return 1 if errors else 0


def safe_slug(value):
    slug = re.sub(r'[^a-z0-9-]+', '-', value.lower()).strip('-')
    return slug[:64] or 'research-domain'


def cmd_init(args):
    d = Path(args.directory)
    if d.exists() and any(d.iterdir()):
        print('目标目录非空，禁止覆盖：', d, file=sys.stderr)
        return 1
    d.mkdir(parents=True, exist_ok=True)
    project = json.loads((TEMPLATES/'project.json').read_text(encoding='utf8'))
    project['project_id'] = safe_slug(args.project_id or d.name)
    project['topic'] = args.topic
    project['scope'] = args.scope or '待定义；不能将其当成已冻结的方向边界'
    write_json(d/'project.json', project)
    write_json(d/'papers.json', [])
    write_json(d/'rules.json', [])
    (d/'screening_log.md').write_text('# 检索与筛选记录\n\n尚未检索。\n', encoding='utf8')
    (d/'evaluation.md').write_text('# 独立评估记录\n\n尚未执行。\n', encoding='utf8')
    print(f'已建立项目：{d}（尚未检索任何论文）')
    return 0


def cmd_freeze(args):
    d = Path(args.directory)
    path = d / 'project.json'
    err = []
    project = load(path, err)
    if err or not isinstance(project, dict):
        print('不能冻结：' + '; '.join(err), file=sys.stderr)
        return 1
    part = project.get(args.part)
    if not isinstance(part, dict):
        print(f'缺少 {args.part} 对象', file=sys.stderr)
        return 1
    if part.get('frozen'):
        if part.get('fingerprint') == fingerprint(part):
            print(f'{args.part} 已冻结，指纹有效；未作修改')
            return 0
        print(f'{args.part} 已冻结但内容变化；请人工检查版本，不能直接重新冻结', file=sys.stderr)
        return 1
    if args.part == 'protocol' and not all(isinstance(part.get(x), list) and part.get(x)
                                           for x in ('sources', 'queries', 'inclusion', 'exclusion')):
        print('检索协议必须填写 sources, queries, inclusion, exclusion 才可冻结', file=sys.stderr)
        return 1
    if args.part == 'evaluation':
        errs, _, _, _, _ = audit(d)
        blockers = [e for e in errs if 'holdout_id' in e or '为 holdout' in e]
        if blockers:
            print('留出集不一致：' + '; '.join(blockers), file=sys.stderr)
            return 1
        if not part.get('holdout_ids'):
            print('没有留出论文，请先标记 holdout 再冻结独立评估计划', file=sys.stderr)
            return 1
    part['frozen'] = True
    part['frozen_at'] = now_utc()
    part['fingerprint'] = fingerprint(part)
    write_json(path, project)
    print(f'已冻结 {args.part}；后续修改将触发结构错误')
    return 0


def escape_md(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def cmd_compile(args):
    d = Path(args.directory)
    errs, warns, project, papers, rules = audit(d)
    if errs:
        print('证据结构有错误，不能生成：', *errs, sep='\n- ', file=sys.stderr)
        return 1
    if not project['protocol']['frozen'] or not project['evaluation']['frozen']:
        print('必须先冻结检索协议和留出评估计划才能编译', file=sys.stderr)
        return 1
    accepted = [r for r in rules if r['status'] in ('reviewed', 'tested')]
    preview = args.preview
    if preview:
        accepted = rules
    if not accepted:
        print('没有已审查的规则；可用 --preview 生成未验证的草稿', file=sys.stderr)
        return 1
    out = d / 'generated_skill'
    if out.exists() and not args.force:
        print('generated_skill 已存在；若确实需要覆盖请传 --force', file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    (out/'references').mkdir(exist_ok=True)
    title = project['topic']
    skillname = 'gewu-' + safe_slug(project['project_id'])[:45]
    note = '候选规则预览，未经完整证据审查；禁止将其当作领域结论。' if preview else '引用已被记录为人工核查；独立科学有效性仍须单独评估。'
    lines = [
        '---', f'name: {skillname}',
        'description: ' + json.dumps(f'基于 {title} 研究文献生成的条件性科研方法 Skill；检索与证据可能有局限，需核查原始来源。', ensure_ascii=False),
        '---', '', f'# {title} · 研究方向 Skill', '', f'> {note}', '',
        '## 适用边界', '', project['scope'], '', '## 行动准则', '',
        '1. 先确定可检验的科学问题、数据条件和失败判据。',
        '2. 只使用 `references/rules.md` 中适用条件满足的规则；逐条展示证据与边界。',
        '3. 不能从发表频率推断最佳方法，不能把研究假说写成已证事实。',
        '4. 涉及冲突结果时先比较研究条件，不强行合并。',
        '5. 实验协议与评估指标先冻结，结果欠佳时不能静默调整。',
        '6. 期刊选择发生在研究贡献明确之后。',
        '', '## 规则索引', ''
    ]
    for r in accepted:
        lines.append(f"- **{r['rule_id']}** — {r['statement']}（{r['status']}；{r['kind']}）")
    lines += ['', '详细证据、相反研究及适用边界见 `references/rules.md`。',
              '', '## 证据状态', '',
              f'规则数量：{len(accepted)}；预览模式：{"是" if preview else "否"}。',
              '该 Skill 由本地结构化记录编译；工具未检索外部数据库，也未独立核对科学真实性。', '']
    (out/'SKILL.md').write_text('\n'.join(lines), encoding='utf8')
    detail = ['# 条件性科研规则与证据索引', '', f'> {note}', '']
    paper_map = {p['paper_id']: p for p in papers}
    for r in accepted:
        detail += [f"## {r['rule_id']} · {r['question']}", '',
                   f"- 性质与状态：{r['kind']} / {r['status']}",
                   f"- IF（条件）：{r['condition']}",
                   f"- THEN（行动）：{r['action']}",
                   f"- WHY（依据）：{r['rationale']}",
                   f"- 边界：{r['limits']}", '', '支持证据：', '']
        for e in r['evidence']:
            p = paper_map[e['paper_id']]
            detail.append(f"- [{e['paper_id']}] {escape_md(p['title'])}；{e['locator']}；{e['summary']}（人工核查标记：{e['review_status']}）")
        detail += ['', '反例与相反证据：', '']
        for e in r['counterexamples']:
            p = paper_map[e['paper_id']]
            detail.append(f"- [{e['paper_id']}] {escape_md(p['title'])}；{e['locator']}；{e['summary']}")
        if not r['counterexamples']:
            detail.append('- 当前未记录反例，不等于不存在。')
        sr = r['counterexample_search']
        detail += ['', f"反例检索：{sr['status']}；{sr.get('notes', '')}", '']
    (out/'references'/'rules.md').write_text('\n'.join(detail), encoding='utf8')
    print(f'生成成功：{out / "SKILL.md"}\n规则 {len(accepted)} 条；科学有效性尚需独立评估。')
    return 0


def cmd_report(args):
    errors, warnings, project, papers, rules = audit(args.directory)
    counts = {key: sum(1 for p in papers if isinstance(p, dict) and p.get('access_level') == key)
              for key in ACCESS_LEVELS}
    print('项目：', project.get('topic', '(缺失)'))
    print('论文总数：', len(papers), '可读全文：', counts['fulltext'],
          '仅摘要：', counts['abstract'], '仅元数据：', counts['metadata'])
    print('规则总数：', len(rules), '已审查：', sum(1 for r in rules if isinstance(r,dict) and r.get('status') == 'reviewed'))
    print('留出论文数：', len(project.get('evaluation',{}).get('holdout_ids',[])))
    print('配置已冻结：检索协议=', bool(project.get('protocol',{}).get('frozen')),
          '评估计划=', bool(project.get('evaluation',{}).get('frozen')))
    print('结构错误：', len(errors), '提醒：', len(warnings))
    print('当前报告是元数据与内部一致性统计，不是文献研究结果。')
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='GEWU Research Edition — local skill toolkit')
    sub = parser.add_subparsers(dest='cmd', required=True)
    init = sub.add_parser('init', help='初始化科研方向项目')
    init.add_argument('directory')
    init.add_argument('--topic', required=True)
    init.add_argument('--scope')
    init.add_argument('--project-id')
    init.set_defaults(fn=cmd_init)
    check = sub.add_parser('check', help='结构及引用检查')
    check.add_argument('directory')
    check.set_defaults(fn=lambda a: print_audit(a.directory))
    freeze = sub.add_parser('freeze', help='冻结检索协议或独立评估计划')
    freeze.add_argument('directory')
    freeze.add_argument('--part', choices=('protocol', 'evaluation'), required=True)
    freeze.set_defaults(fn=cmd_freeze)
    compile_cmd = sub.add_parser('compile', help='将已审查规则编译为方向 Skill')
    compile_cmd.add_argument('directory')
    compile_cmd.add_argument('--preview', action='store_true', help='草稿预览，包含未核查规则')
    compile_cmd.add_argument('--force', action='store_true', help='覆盖本地生成目录')
    compile_cmd.set_defaults(fn=cmd_compile)
    report = sub.add_parser('report', help='汇总项目记录状态')
    report.add_argument('directory')
    report.set_defaults(fn=cmd_report)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
