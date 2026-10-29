"""Synthetic-only tests: none of the paper entries correspond to real studies."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills'/'gewu'/'scripts'))
from gewu import audit, cmd_compile, cmd_freeze, cmd_init, fingerprint


class Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf8')


class GewuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)/'project'
        result = cmd_init(Args(directory=str(self.d), topic='合成研究方向', scope='合成测试，非真实文献', project_id='test'))
        self.assertEqual(result, 0)

    def read(self, name):
        return json.loads((self.d/name).read_text(encoding='utf8'))

    def prepare(self, with_rule=True):
        project = self.read('project.json')
        project['protocol'].update(sources=['synthetic database'], queries=['synthetic query'],
                                   inclusion=['test'], exclusion=['outside'])
        save(self.d/'project.json', project)
        self.assertEqual(cmd_freeze(Args(directory=str(self.d), part='protocol')), 0)
        papers = []
        for pid, pool in [('P1','synthesis'), ('P2','synthesis'), ('P3','holdout')]:
            papers.append(dict(paper_id=pid, title=f'[SYNTHETIC] Paper {pid}',
                access_level='fulltext', pool=pool,
                screening={'decision':'included','reason':'synthetic test only'},
                url=f'https://example.invalid/{pid}'))
        save(self.d/'papers.json', papers)
        project = self.read('project.json')
        project['evaluation']['holdout_ids'] = ['P3']
        save(self.d/'project.json', project)
        self.assertEqual(cmd_freeze(Args(directory=str(self.d), part='evaluation')), 0)
        if with_rule:
            ev = [dict(paper_id=pid, locator='Section 2 / Table 1',
                   summary='Synthetic evidence; not a scientific claim', source_part='methods',
                   review_status='checked') for pid in ['P1', 'P2']]
            rules = [dict(rule_id='R001', question='How to test?', statement='Synthetic rule',
                condition='synthetic condition', action='synthetic action', rationale='synthetic rationale',
                limits='only for tests', kind='recommendation', status='reviewed', evidence=ev,
                counterexamples=[], counterexample_search={'status':'searched','notes':'synthetic test'})]
            save(self.d/'rules.json', rules)

    def test_empty_project_is_structurally_valid_with_warnings(self):
        errors, warnings, *_ = audit(self.d)
        self.assertEqual(errors, [])
        self.assertTrue(any('没有论文' in w for w in warnings))

    def test_unknown_paper_id_is_rejected(self):
        self.prepare()
        rules = self.read('rules.json')
        rules[0]['evidence'][0]['paper_id'] = 'P999'
        save(self.d/'rules.json', rules)
        errors, *_ = audit(self.d)
        self.assertTrue(any('不存在的 paper_id' in e for e in errors))

    def test_holdout_leakage_is_rejected(self):
        self.prepare()
        rules = self.read('rules.json')
        rules[0]['evidence'][0]['paper_id'] = 'P3'
        save(self.d/'rules.json', rules)
        errors, *_ = audit(self.d)
        self.assertTrue(any('禁止把留出论文' in e for e in errors))

    def test_abstract_does_not_justify_methods(self):
        self.prepare()
        papers = self.read('papers.json')
        papers[0]['access_level'] = 'abstract'
        save(self.d/'papers.json', papers)
        errors, *_ = audit(self.d)
        self.assertTrue(any('证据来源层级超出' in e for e in errors))

    def test_reviewed_requires_checked_evidence(self):
        self.prepare()
        rules = self.read('rules.json')
        rules[0]['evidence'][0]['review_status'] = 'unchecked'
        save(self.d/'rules.json', rules)
        errors, *_ = audit(self.d)
        self.assertTrue(any('逐项人工核对' in e for e in errors))

    def test_freeze_lock_detects_revisions(self):
        self.prepare()
        project = self.read('project.json')
        project['protocol']['queries'].append('new query after freeze')
        save(self.d/'project.json', project)
        errors, *_ = audit(self.d)
        self.assertTrue(any('已冻结配置被更改' in e for e in errors))

    def test_compiles_only_reviewed_rules(self):
        self.prepare()
        rules = self.read('rules.json')
        draft = copy.deepcopy(rules[0])
        draft['rule_id'] = 'R002'
        draft['statement'] = 'UNVERIFIED CANDIDATE'
        draft['status'] = 'candidate'
        draft['evidence'][0]['review_status'] = 'unchecked'
        save(self.d/'rules.json', rules + [draft])
        result = cmd_compile(Args(directory=str(self.d), preview=False, force=False))
        self.assertEqual(result, 0)
        output = (self.d/'generated_skill'/'SKILL.md').read_text(encoding='utf8')
        self.assertIn('R001', output)
        self.assertNotIn('R002', output)
        self.assertTrue((self.d/'generated_skill'/'references'/'rules.md').exists())

    def test_compile_fails_without_rules(self):
        self.prepare(with_rule=False)
        result = cmd_compile(Args(directory=str(self.d), preview=False, force=False))
        self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()
