#!/usr/bin/env python3
"""GEWU v0.3: PDF-to-evidence and evidence-to-candidate-rule pipeline.

Local PDF processing is offline. LLM mode is explicit and uses a user-selected
OpenAI-compatible chat/completions endpoint. Generated claims are NEVER reviewed.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from gewu import audit, load, now_utc, write_json

ALLOWED_FIELDS = ('research_question', 'hypothesis', 'data', 'method', 'baselines',
                  'evaluation', 'results', 'limitations')
LABELS = {'research_question': '研究问题', 'hypothesis': '研究假设',
          'data': '数据', 'method': '研究方法', 'baselines': '对照方法',
          'evaluation': '验证与评价', 'results': '主要结果', 'limitations': '局限与反例'}
KEYWORDS = {
    'research_question': r'objective|research question|aim of|we investigate|目的|研究问题|旨在',
    'hypothesis': r'hypothes|we expect|we posit|假设|预期',
    'data': r'dataset|data source|observations|study area|数据|研究区|观测',
    'method': r'method|model|algorithm|framework|approach|方法|模型|算法',
    'baselines': r'baseline|benchmark|comparison model|对照|基线',
    'evaluation': r'validation|test set|metric|evaluation|验证|评价指标|测试集',
    'results': r'result|we found|outperform|improve|结果|发现|提升',
    'limitations': r'limitation|future work|uncertainty|however|局限|不足|未来|不确定性',
}
HEADING = re.compile(r'^\s*(?:(?:\d+(?:\.\d+)*\s+)|(?:[IVX]+[.)]\s+))?'
                     r'(abstract|introduction|background|literature review|study area|'
                     r'materials? and methods?|methodology|methods?|experiments?|results?(?: and discussion)?|'
                     r'discussion|conclusions?|limitations?|references|acknowledgments?|'
                     r'摘要|引言|绪论|研究区|数据|材料与方法|研究方法|实验|结果与讨论|结果|讨论|结论|局限|参考文献)\s*$'
                     , re.I)
DOI_RE = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.I)
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
PART_HINT = {
    'abstract': 'abstract', '摘要': 'abstract', 'introduction': 'introduction', 'background': 'introduction',
    'study area': 'methods', 'method': 'methods', 'materials': 'methods', 'experiment': 'methods',
    '研究区': 'methods', '数据': 'methods', '方法': 'methods', '实验': 'methods',
    'result': 'results', '结果': 'results', 'discussion': 'discussion', '讨论': 'discussion',
    'conclusion': 'conclusion', '结论': 'conclusion', 'limitations': 'discussion', '局限': 'discussion',
    'references': 'references', '参考文献': 'references',
}


def read_json(path):
    errors = []
    data = load(path, errors)
    if errors:
        raise ValueError('; '.join(errors))
    return data


def hash_file(path):
    sha = hashlib.sha256()
    with open(path, 'rb') as fh:
        for data in iter(lambda: fh.read(1024 * 1024), b''):
            sha.update(data)
    return sha.hexdigest()


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def classify_heading(line):
    match = HEADING.match(normalized(line))
    if not match:
        return None
    low = match.group(1).lower()
    for key, val in PART_HINT.items():
        if key in low:
            return val
    return 'other'


def pdf_to_passages(pdf, pid, chunk_chars=1700):
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError('缺少 PyMuPDF；请运行 pip install -r requirements.txt') from exc
    try:
        doc = fitz.open(pdf)
    except Exception as exc:
        raise ValueError(f'PDF 无法打开：{exc}') from exc
    passages = []
    alltext = []
    section = 'other'
    for pindex, page in enumerate(doc):
        # sort=True is a best-effort reading order, not reliable for complex columns/tables.
        raw = page.get_text('text', sort=True)
        lines = [normalized(x) for x in raw.splitlines()]
        lines = [x for x in lines if x]
        alltext.extend(lines)
        buffered, start = [], None
        def flush():
            nonlocal buffered, start
            if not buffered:
                return
            body = '\n'.join(buffered)
            seq = len(passages) + 1
            passages.append({'passage_id': f'{pid}:S{seq:05}', 'paper_id': pid,
                'page': pindex + 1, 'line_start': start, 'line_end': last,
                'source_part': section, 'text': body,
                'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest()})
            buffered, start = [], None
        last = 0
        for line_no, text in enumerate(lines, 1):
            tag = classify_heading(text)
            if tag:
                flush()
                section = tag
                continue
            if start is None:
                start = line_no
            if sum(len(x) for x in buffered) + len(text) + 1 > chunk_chars and buffered:
                flush()
                start = line_no
            buffered.append(text)
            last = line_no
        flush()
    doc.close()
    return passages, ' '.join(alltext)


def cmd_ingest(args):
    if not ID_RE.fullmatch(args.id):
        raise ValueError('论文 ID 只允许 1–64 位字母、数字、下划线或连字符')
    base, pdf = Path(args.directory), Path(args.pdf)
    if not pdf.is_file() or pdf.suffix.lower() != '.pdf':
        raise ValueError('请提供已有的本地 PDF 文件')
    project = read_json(base / 'project.json')
    if project.get('evaluation', {}).get('frozen'):
        raise ValueError('评估计划已经冻结；不得新增或重分配论文。请新建研究版本。')
    papers = read_json(base / 'papers.json')
    if not isinstance(papers, list):
        raise ValueError('papers.json 格式错误')
    existing = next((p for p in papers if p['paper_id'] == args.id), None)
    if existing and not args.replace:
        raise ValueError(f'论文 {args.id} 已存在；不得静默覆盖')
    if existing and existing['pool'] != args.pool:
        raise ValueError('不得用 --replace 修改论文所属综合集/留出集')
    if existing and (base/'extracts'/f'{args.id}.json').exists():
        raise ValueError('该论文已有提取结果。请建立新版本，不能仅替换 PDF 使证据与原文失配')
    sha = hash_file(pdf)
    passages, full_text = pdf_to_passages(pdf, args.id)
    if len(full_text.strip()) < 250:
        raise ValueError('可提取文本不足250字符，可能为扫描/图片 PDF；需人工/OCR处理，不标记为全文')
    doi = args.doi or (DOI_RE.search(full_text[:12000]).group(0).rstrip('.,;') if DOI_RE.search(full_text[:12000]) else None)
    title = args.title
    if not title:
        raise ValueError('必须提供 --title（避免把页眉或 PDF 文件名误认作论文题名）')
    if any(p.get('doi') and doi and p['paper_id'] != args.id and
           p['doi'].lower().replace('https://doi.org/','') == doi.lower().replace('https://doi.org/','') for p in papers):
        raise ValueError('DOI 与已有论文重复')
    if args.pool == 'holdout' and read_json(base/'rules.json'):
        raise ValueError('规则已开始归纳，不能事后建立新的留出集')
    (base/'corpus').mkdir(exist_ok=True)
    out = base/'corpus'/f'{args.id}.json'
    if out.exists() and not args.replace:
        raise ValueError('同 ID 的解析语料已存在')
    source = {'schema_version': '0.3', 'paper_id': args.id, 'pdf_filename': pdf.name,
              'pdf_sha256': sha, 'parsed_at': now_utc(), 'page_count': max(p['page'] for p in passages),
              'char_count': len(full_text), 'parser': 'PyMuPDF text(sort=True)',
              'limitations': ['双栏、表格、公式和脚注可能出现阅读顺序或字符错误；未执行 OCR'],
              'passages': passages}
    paper = {'paper_id': args.id, 'title': title, 'authors': [], 'year': None,
             'venue': None, 'doi': doi, 'url': args.url, 'version': 'unspecified',
             'access_level': 'fulltext', 'pool': args.pool,
             'screening': {'decision': 'included', 'reason': '用户提供 PDF；纳排标准仍须人工核查'},
             'extraction': {key: [] for key in ALLOWED_FIELDS},
             'pdf_sha256': sha, 'corpus_path': f'corpus/{args.id}.json',
             'bibliography_status': 'unverified',
             'fulltext_status': 'machine_extracted_unreviewed'}
    # Write only after all checks are complete.
    papers = [p for p in papers if p['paper_id'] != args.id] + [paper]
    write_json(out, source)
    write_json(base/'papers.json', papers)
    print(f'已解析 {args.id}：{source["page_count"]} 页 / {len(passages)} 段；PDF SHA256={sha[:16]}…')
    print('警告：论文元数据和排版内容未经人工核查；需要核对复杂表格和公式。')
    return 0


def source_records(base, pid):
    source = read_json(base/'corpus'/f'{pid}.json')
    pmap = {p['paper_id']: p for p in read_json(base/'papers.json')}
    if pid not in pmap:
        raise ValueError(f'未登记论文 {pid}')
    paper = pmap[pid]
    if paper.get('pdf_sha256') != source.get('pdf_sha256'):
        raise ValueError(f'{pid} 语料哈希与论文记录不匹配')
    return paper, source


def snippet_candidates(source, per_field=7):
    out = {field: [] for field in ALLOWED_FIELDS}
    for passage in source['passages']:
        if passage['source_part'] == 'references':
            continue
        for field in ALLOWED_FIELDS:
            if len(out[field]) >= per_field:
                continue
            pattern = re.compile(KEYWORDS[field], re.I)
            sentences = re.split(r'(?<=[.!?。！？])\s+|\n', passage['text'])
            for sent in sentences:
                if pattern.search(sent) and len(sent) > 18:
                    quote = sent[:550].strip()
                    if not any(x['passage_id'] == passage['passage_id'] and x['quote'] == quote for x in out[field]):
                        out[field].append({'passage_id': passage['passage_id'],
                                           'quote': quote, 'page': passage['page'],
                                           'source_part': passage['source_part'],
                                           'claim': None, 'review_status': 'unchecked'})
                    if len(out[field]) >= per_field:
                        break
    return out


def llm_call(args, system, user):
    if not args.allow_external:
        raise ValueError('访问外部模型前必须显式指定 --allow-external（PDF 片段可能离开本机）')
    key = os.environ.get(args.api_key_env)
    if not key:
        raise ValueError(f'缺少环境变量 {args.api_key_env}，禁止继续调用外部服务')
    if not args.model or not args.base_url:
        raise ValueError('外部模型必须提供 --model 和 --base-url')
    endpoint = args.base_url.rstrip('/') + '/chat/completions'
    if not endpoint.startswith('https://') and not args.allow_http:
        raise ValueError('只允许 HTTPS；测试本地服务可显式使用 --allow-http')
    req_data = json.dumps({'model': args.model, 'temperature': 0,
                           'messages': [{'role':'system', 'content':system},
                                        {'role':'user', 'content':user}]}).encode('utf8')
    request = urllib.request.Request(endpoint, req_data,
           {'Authorization': 'Bearer '+key, 'Content-Type':'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as res:
            response = json.loads(res.read(12_000_000).decode('utf8'))
        content = response['choices'][0]['message']['content'].strip()
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
        return json.loads(content)
    except (OSError, urllib.error.URLError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ValueError(f'外部模型访问或输出 JSON 解析失败：{exc}') from exc


def validated_model_extract(result, provided, source):
    if not isinstance(result, dict):
        raise ValueError('模型输出必须是 JSON 对象')
    index = {p['passage_id']: p for p in source['passages']}
    allowed = set(provided)
    outcome = {field: [] for field in ALLOWED_FIELDS}
    for field, records in result.items():
        if field not in ALLOWED_FIELDS or not isinstance(records, list):
            raise ValueError('模型使用了未知提取字段')
        for item in records:
            if not isinstance(item, dict):
                raise ValueError('提取条目必须是对象')
            pid, quote, claim = item.get('passage_id'), item.get('quote'), item.get('claim')
            if pid not in allowed or pid not in index or not isinstance(quote, str) or not quote.strip():
                raise ValueError(f'无效来源 ID / 引文：{pid}')
            if normalized(quote) not in normalized(index[pid]['text']):
                raise ValueError(f'模型所引原文不匹配：{pid}')
            if not isinstance(claim, str) or not claim.strip():
                raise ValueError('claim 不能为空')
            rec = index[pid]
            outcome[field].append({'passage_id':pid, 'quote':quote,
                 'page':rec['page'], 'source_part':rec['source_part'],
                 'claim':claim.strip(), 'review_status':'unchecked'})
    return outcome


def cmd_extract(args):
    base = Path(args.directory)
    paper, source = source_records(base, args.id)
    if args.max_passages < 1:
        raise ValueError('--max-passages 必须大于零')
    if paper.get('pool') == 'holdout':
        raise ValueError('留出论文不应进入综合提取流程；请另行开展独立验证')
    candidates = snippet_candidates(source)
    if args.provider == 'local':
        outcome = candidates
        mode = 'keyword_passage_candidates'
    else:
        # Only a bounded sample reaches the model; list omissions in the file.
        ordered = []
        ids = set()
        for field in ALLOWED_FIELDS:
            for candidate in candidates[field]:
                pid = candidate['passage_id']
                if pid not in ids:
                    ordered.append(pid)
                    ids.add(pid)
        selected = ordered[:args.max_passages]
        index = {p['passage_id']:p for p in source['passages']}
        user = json.dumps({'title':paper['title'], 'passages':[
            {'passage_id':pid, 'page':index[pid]['page'], 'text':index[pid]['text']}
            for pid in selected]}, ensure_ascii=False)
        system = ("你是科研论文证据提取器。仅返回严格 JSON 对象，键仅能是 "
                  + ','.join(ALLOWED_FIELDS) + "。每个条目必须包含 passage_id、quote、claim。"
                  "quote 必须逐字来自给定 passage_id；claim 为中文保守复述，不可推测全文、表格数值或 DOI。"
                  "找不到证据时给空数组。明确区分论文作者的论述和客观事实。")
        result = llm_call(args, system, user)
        outcome = validated_model_extract(result, selected, source)
        mode = 'llm_candidates_unreviewed'
    (base/'extracts').mkdir(exist_ok=True)
    data = {'schema_version':'0.3', 'paper_id':args.id, 'pdf_sha256':source['pdf_sha256'],
            'mode':mode, 'model': args.model if args.provider == 'llm' else None,
            'generated_at':now_utc(), 'passages_total':len(source['passages']),
            'coverage_warning': '词汇召回和段落截断不能保证覆盖所有实验细节或反例',
            'entries':outcome}
    path = base/'extracts'/f'{args.id}.json'
    if path.exists() and read_json(base/'rules.json'):
        raise ValueError('已有跨论文规则；不得替换其来源提取，必须创建新的项目版本')
    if path.exists() and not args.replace:
        raise ValueError('提取文件已存在；使用 --replace 明确替换（需留下版本记录）')
    write_json(path, data)
    papers = read_json(base/'papers.json')
    for p in papers:
        if p['paper_id'] == args.id:
            p['extraction'] = outcome
            p['extraction_status'] = mode
    write_json(base/'papers.json', papers)
    print(f'候选提取已保存：{path}；{sum(map(len,outcome.values()))} 个原文片段，均未人工核查。')
    return 0


def evidence_inventory(base):
    papers = read_json(base/'papers.json')
    project = read_json(base/'project.json')
    if not project['protocol']['frozen'] or not project['evaluation']['frozen']:
        raise ValueError('蒸馏前必须冻结检索协议和留出评价计划')
    errs, _, _, _, _ = audit(base)
    if errs:
        raise ValueError('既有记录审查未通过：' + '; '.join(errs))
    inventory = []
    for paper in papers:
        if paper.get('pool') != 'synthesis' or paper['screening']['decision'] != 'included':
            continue
        path = base/'extracts'/f'{paper["paper_id"]}.json'
        if not path.exists():
            continue
        ext = read_json(path)
        if ext.get('pdf_sha256') != paper.get('pdf_sha256'):
            raise ValueError('提取文件与原始论文的哈希不符')
        corpus = read_json(base/'corpus'/f'{paper["paper_id"]}.json')
        if corpus.get('pdf_sha256') != paper.get('pdf_sha256'):
            raise ValueError('语料指纹与论文记录不同')
        lookup = {item['passage_id']: item for item in corpus['passages']}
        for passage in lookup.values():
            if passage.get('sha256') != hashlib.sha256(passage['text'].encode('utf8')).hexdigest():
                raise ValueError('语料片段的文本哈希不匹配；不得继续蒸馏')
        for field, entries in ext.get('entries', {}).items():
            if field not in ALLOWED_FIELDS:
                raise ValueError('未知提取类别')
            for item in entries:
                ref = lookup.get(item.get('passage_id'))
                if ref is None or not isinstance(item.get('quote'), str) or \
                        normalized(item['quote']) not in normalized(ref['text']):
                    raise ValueError('候选证据的原文或 passage_id 与 PDF 语料不匹配')
                if item.get('page') != ref['page'] or item.get('source_part') != ref['source_part']:
                    raise ValueError('候选证据页码或章节位置与 PDF 语料不一致')
                inventory.append({'evidence_id': f'{paper["paper_id"]}|{field}|{len(inventory):05}',
                                  'paper_id':paper['paper_id'], 'title':paper['title'],
                                  'field':field, **item})
    if not inventory:
        raise ValueError('没有可用的综合集证据；先 ingest / extract')
    return inventory


def valid_synthesis_result(result, inventory):
    if not isinstance(result, dict) or not isinstance(result.get('rules'), list):
        raise ValueError('模型须返回 {"rules": [...]}')
    lookup = {e['evidence_id']:e for e in inventory}
    rules = []
    for k, item in enumerate(result['rules']):
        if not isinstance(item, dict):
            raise ValueError('规则项格式错误')
        fields = ('question','statement','condition','action','rationale','limits')
        if any(not isinstance(item.get(x),str) or not item[x].strip() for x in fields):
            raise ValueError('规则缺少核心字段')
        evid_ids = item.get('evidence_ids')
        if not isinstance(evid_ids, list) or not evid_ids or len(set(evid_ids)) != len(evid_ids):
            raise ValueError('规则证据引用不可为空或重复')
        if any(eid not in lookup for eid in evid_ids):
            raise ValueError('模型引用未知证据或留出证据')
        # Only genuinely cross-paper rules are allowed in this v0.3 command.
        if len({lookup[eid]['paper_id'] for eid in evid_ids}) < 2:
            raise ValueError('跨论文规则必须引用至少两篇不同论文')
        evidences=[]
        for eid in evid_ids:
            e=lookup[eid]
            evidences.append({'paper_id':e['paper_id'], 'locator':f'p.{e["page"]} / {e["passage_id"]}',
                              'summary': e.get('claim') or e['quote'],
                              'source_part':e['source_part'],
                              'review_status':'unchecked'})
        rules.append({'rule_id':f'R{k+1:03}', **{x:item[x].strip() for x in fields},
                      'kind':'recommendation', 'status':'candidate', 'evidence':evidences,
                      'counterexamples':[],
                      'counterexample_search':{'status':'not_started','notes':'模型生成规则后必须开展反例检索'},
                      'generation':'llm_unreviewed'})
    return rules


def cmd_synthesize(args):
    base = Path(args.directory)
    inv = evidence_inventory(base)
    if args.max_evidence < 2:
        raise ValueError('--max-evidence 必须至少为 2')
    (base/'analysis').mkdir(exist_ok=True)
    matrix={'schema_version':'0.3', 'generated_at':now_utc(), 'type':'evidence_matrix',
            'note':'此文件仅并排整理真实 PDF 片段或模型候选解释；不是跨论文科学结论',
            'by_field':{f:[e for e in inv if e['field']==f] for f in ALLOWED_FIELDS}}
    write_json(base/'analysis'/'evidence_matrix.json',matrix)
    if args.provider=='local':
        print(f'已输出跨论文证据矩阵：{len(inv)} 条候选片段；未自动生成科研结论或 rules.json。')
        return 0
    unique={e['paper_id'] for e in inv}
    if len(unique)<2:
        raise ValueError('需要至少两篇已提取的综合集论文，才能生成跨论文候选规则')
    # Round-robin across papers: avoid an early, long paper consuming all evidence slots.
    by_paper=defaultdict(list)
    for e in inv:
        by_paper[e['paper_id']].append(e)
    subset=[]
    while len(subset)<args.max_evidence and any(by_paper.values()):
        for pid in sorted(by_paper):
            if by_paper[pid] and len(subset)<args.max_evidence:
                subset.append(by_paper[pid].pop(0))
    system=("你是跨论文科研方法比较器。仅返回 JSON {\"rules\": [...]}，每条必须提供 question,"
            "statement,condition,action,rationale,limits,evidence_ids 字段。"
            "每条规则引用至少两篇不同论文的 evidence_id。只能依据提供的来源提出条件性科研设计建议，"
            "不得宣称最优、共识或因果；不得编造 DOI、图表或论文结果。没足够证据则返回空数组。")
    data=llm_call(args,system,json.dumps({'topic':read_json(base/'project.json')['topic'],
                   'evidence':subset},ensure_ascii=False))
    rules=valid_synthesis_result(data,subset)
    existing=read_json(base/'rules.json')
    if existing and not args.replace:
        raise ValueError('已有 rules.json 非空；先人工检查再用 --replace 明确覆盖候选规则')
    if any(r.get('status') in ('reviewed','tested') for r in existing):
        raise ValueError('不能覆盖已审查的科研规则，请新建项目版本')
    write_json(base/'analysis'/'synthesis_trace.json',{
         'generated_at':now_utc(), 'model':args.model,'source_evidence_ids':[e['evidence_id'] for e in subset],
         'note':'LLM 规则仅为候选；证据引文的真实性应回看 PDF；尚未开展反例检索'})
    write_json(base/'rules.json', rules)
    print(f'生成 {len(rules)} 条跨论文候选规则；全部 status=candidate，证据 unchecked。')
    return 0


def add_model_args(parser):
    parser.add_argument('--provider',choices=('local','llm'),default='local')
    parser.add_argument('--allow-external', action='store_true', help='明确同意向模型服务发送 PDF 片段')
    parser.add_argument('--allow-http', action='store_true', help='仅限可控本地测试环境')
    parser.add_argument('--base-url', default=os.environ.get('GEWU_LLM_BASE_URL','https://api.openai.com/v1'))
    parser.add_argument('--model', default=os.environ.get('GEWU_LLM_MODEL'))
    parser.add_argument('--api-key-env', default='OPENAI_API_KEY')
    parser.add_argument('--timeout',type=int,default=90)


def main(argv=None):
    parser=argparse.ArgumentParser(description='GEWU v0.3: local PDF extraction and cross-paper synthesis')
    sub=parser.add_subparsers(dest='command',required=True)
    ing=sub.add_parser('ingest',help='将本地真实 PDF 解析为带页码/指纹的证据片段')
    ing.add_argument('directory');ing.add_argument('--pdf',required=True)
    ing.add_argument('--id',required=True);ing.add_argument('--title',required=True)
    ing.add_argument('--doi');ing.add_argument('--url');ing.add_argument('--pool',choices=('synthesis','holdout'),default='synthesis')
    ing.add_argument('--replace',action='store_true');ing.set_defaults(func=cmd_ingest)
    ext=sub.add_parser('extract',help='依据原文片段提取科研问题与研究方法候选')
    ext.add_argument('directory');ext.add_argument('--id',required=True)
    ext.add_argument('--max-passages',type=int,default=35);ext.add_argument('--replace',action='store_true')
    add_model_args(ext);ext.set_defaults(func=cmd_extract)
    syn=sub.add_parser('synthesize',help='生成证据矩阵，或可选的跨论文候选规则')
    syn.add_argument('directory');syn.add_argument('--max-evidence',type=int,default=110)
    syn.add_argument('--replace',action='store_true');add_model_args(syn);syn.set_defaults(func=cmd_synthesize)
    args=parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())