"""Synthetic test documents only. Never use test fixture prose as scientific evidence."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE/'skills'/'gewu'/'scripts'))
import gewu
import gewu_v03 as pipe

class Args:
    def __init__(self, **kw): self.__dict__.update(kw)


def write(path, val):
    path.write_text(json.dumps(val,ensure_ascii=False,indent=2), encoding='utf8')


def make_pdf(path, text, pages=2):
    c = canvas.Canvas(str(path))
    for n in range(pages):
        y = 770
        for ln in text.splitlines():
            c.drawString(45,y,ln[:110])
            y -= 15
        c.drawString(45,120, f'Page {n+1} synthetic test fixture only. No authentic results.')
        c.showPage()
    c.save()


DOC='''Synthetic paper title
Abstract
The objective of this synthetic method study is to investigate model comparison under test conditions.
Introduction
We investigate how baseline controls affect the evaluation in a research design. The hypothesis is only a synthetic test claim.
Methods
Our model method uses synthetic observations, a mock dataset, and a baseline comparison model for controlled evaluation.
Results
Our results in this imaginary experiment show that testing metrics must be compared cautiously and repeatably.
Discussion
However the limitations of this synthetic model prevent any actual hydrological claim outside the test.
References
A reference text that is only part of this synthetic exercise and does not cite a real paper.
'''


class TestV03(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.d = self.root/'project'
        gewu.cmd_init(Args(directory=str(self.d),topic='合成测试',scope='非真实科学研究',project_id='test'))
        self.pdfs = []
        for n in range(3):
            p=self.root/f'P{n}.pdf'
            make_pdf(p,DOC)
            self.pdfs.append(p)

    def ingest(self,i,pool='synthesis'):
        return pipe.cmd_ingest(Args(directory=str(self.d),pdf=str(self.pdfs[i]),id=f'P{i}',title=f'Synthetic {i}',
            doi=None,url=f'https://example.invalid/{i}',pool=pool,replace=False))

    def extract(self,i,provider='local',**kwargs):
        args=dict(directory=str(self.d),id=f'P{i}',provider=provider,replace=False,max_passages=35,
              model=None,allow_external=False,allow_http=False,base_url='https://api.openai.com/v1',
              api_key_env='OPENAI_API_KEY',timeout=90)
        args.update(kwargs)
        return pipe.cmd_extract(Args(**args))

    def freeze(self):
        proj=pipe.read_json(self.d/'project.json')
        proj['protocol'].update(sources=['local PDFs'],queries=['provided PDFs'],
                                inclusion=['synthetic'],exclusion=['other'])
        write(self.d/'project.json',proj)
        self.assertEqual(gewu.cmd_freeze(Args(directory=str(self.d),part='protocol')),0)
        proj=pipe.read_json(self.d/'project.json')
        proj['evaluation']['holdout_ids']=['P2']
        write(self.d/'project.json',proj)
        self.assertEqual(gewu.cmd_freeze(Args(directory=str(self.d),part='evaluation')),0)

    def test_real_pdf_page_and_checksum(self):
        self.ingest(0)
        p=pipe.read_json(self.d/'corpus'/'P0.json')
        self.assertEqual(p['page_count'],2)
        self.assertTrue(all('sha256' in passage and passage['page'] in (1,2) for passage in p['passages']))
        self.assertTrue(any(passage['source_part']=='methods' for passage in p['passages']))
        self.assertEqual(pipe.read_json(self.d/'papers.json')[0]['pdf_sha256'],pipe.hash_file(self.pdfs[0]))

    def test_scanned_pdf_rejection_and_atomic_records(self):
        blank=self.root/'blank.pdf'
        make_pdf(blank,'tiny',1)
        with self.assertRaisesRegex(ValueError,'不足250'):
            pipe.cmd_ingest(Args(directory=str(self.d),pdf=str(blank),id='BAD',title='Blank',
                doi=None,url=None,pool='synthesis',replace=False))
        self.assertEqual(pipe.read_json(self.d/'papers.json'),[])
        self.assertFalse((self.d/'corpus'/'BAD.json').exists())

    def test_no_silent_replace(self):
        self.ingest(0)
        with self.assertRaisesRegex(ValueError,'已存在'):
            self.ingest(0)

    def test_local_candidates_are_not_conclusions(self):
        self.ingest(0)
        self.extract(0)
        ex=pipe.read_json(self.d/'extracts'/'P0.json')
        self.assertEqual(ex['mode'],'keyword_passage_candidates')
        self.assertTrue(any(ex['entries'][key] for key in pipe.ALLOWED_FIELDS))
        for entries in ex['entries'].values():
            for e in entries:
                self.assertIsNone(e['claim'])
                self.assertEqual(e['review_status'],'unchecked')
        self.assertEqual(pipe.read_json(self.d/'rules.json'),[])

    def test_model_quote_verification(self):
        self.ingest(0)
        src=pipe.read_json(self.d/'corpus'/'P0.json')
        passage=src['passages'][0]
        quote=passage['text'][:35]
        good={'research_question':[{'passage_id':passage['passage_id'],'quote':quote,'claim':'合成测试说明'}]}
        out=pipe.validated_model_extract(good,[passage['passage_id']],src)
        self.assertEqual(out['research_question'][0]['quote'],quote)
        bad={'research_question':[{'passage_id':passage['passage_id'],'quote':'Made up quote not in paper','claim':'xx'}]}
        with self.assertRaisesRegex(ValueError,'原文不匹配'):
            pipe.validated_model_extract(bad,[passage['passage_id']],src)

    def test_unknown_source_and_holdout_block(self):
        self.ingest(0)
        self.ingest(2,'holdout')
        with self.assertRaisesRegex(ValueError,'留出论文'):
            self.extract(2)
        with self.assertRaisesRegex(ValueError,'无效来源'):
            pipe.validated_model_extract({'method':[{'passage_id':'P2:S999','quote':'x','claim':'wrong'}]},['P2:S999'],pipe.read_json(self.d/'corpus'/'P0.json'))

    def test_freeze_blocks_late_ingest_and_local_matrix(self):
        for i in range(3): self.ingest(i,'holdout' if i==2 else 'synthesis')
        for i in (0,1): self.extract(i)
        self.freeze()
        with self.assertRaisesRegex(ValueError,'冻结'):
            pipe.cmd_ingest(Args(directory=str(self.d),pdf=str(self.pdfs[0]),id='P4',title='Late',
                doi=None,url=None,pool='synthesis',replace=False))
        params=dict(directory=str(self.d),provider='local',max_evidence=40,replace=False,model=None,
                    allow_external=False,allow_http=False,base_url='https://api.openai.com/v1',
                    api_key_env='OPENAI_API_KEY',timeout=90)
        self.assertEqual(pipe.cmd_synthesize(Args(**params)),0)
        matrix=pipe.read_json(self.d/'analysis'/'evidence_matrix.json')
        ids=[e['paper_id'] for field in matrix['by_field'].values() for e in field]
        self.assertTrue(set(ids)=={'P0','P1'})
        self.assertEqual(pipe.read_json(self.d/'rules.json'),[])

    def test_candidate_rule_checks_source_diversity(self):
        sample=[{'paper_id':'P0','evidence_id':'ev0','page':1,'passage_id':'P0:S1','source_part':'methods',
                 'quote':'Method A','claim':'Method A'},
                {'paper_id':'P1','evidence_id':'ev1','page':2,'passage_id':'P1:S1','source_part':'results',
                 'quote':'Method B','claim':'Method B'}]
        result={'rules':[dict(question='Question',statement='Conditional method choice',
            condition='C', action='A', rationale='R', limits='L',evidence_ids=['ev0','ev1'])]}
        r=pipe.valid_synthesis_result(result,sample)
        self.assertEqual(r[0]['status'],'candidate')
        self.assertEqual(len(r[0]['evidence']),2)
        self.assertTrue(all(e['review_status']=='unchecked' for e in r[0]['evidence']))
        result['rules'][0]['evidence_ids']=['ev0']
        with self.assertRaisesRegex(ValueError,'至少两篇'):
            pipe.valid_synthesis_result(result,sample)
        result['rules'][0]['evidence_ids']=['ev0','nonexistent']
        with self.assertRaisesRegex(ValueError,'未知证据'):
            pipe.valid_synthesis_result(result,sample)


    def test_tampered_quote_fails_synthesis(self):
        for i in range(3): self.ingest(i,'holdout' if i==2 else 'synthesis')
        self.extract(0)
        self.extract(1)
        self.freeze()
        extract=pipe.read_json(self.d/'extracts'/'P0.json')
        field=next(k for k,v in extract['entries'].items() if v)
        extract['entries'][field][0]['quote']='A forged quote not in the paper'
        write(self.d/'extracts'/'P0.json',extract)
        with self.assertRaisesRegex(ValueError,'不匹配'):
            pipe.evidence_inventory(self.d)

    def test_metadata_does_not_override_locked_rules(self):
        for i in range(3): self.ingest(i,'holdout' if i==2 else 'synthesis')
        for i in (0,1): self.extract(i)
        rules=[dict(rule_id='R001', question='q',statement='s',condition='c',action='a',
              rationale='r',limits='l',kind='recommendation',status='candidate',
              evidence=[dict(paper_id='P0',locator='p1',summary='quote',source_part='methods',review_status='unchecked')],
              counterexamples=[],counterexample_search={'status':'not_started','notes':''})]
        write(self.d/'rules.json',rules)
        with self.assertRaisesRegex(ValueError,'不得替换'):
            self.extract(0,replace=True)

    def test_model_extract_path_with_mock(self):
        self.ingest(0)
        # No external HTTP is performed; mock simulates a model returning exact raw PDF evidence.
        src=pipe.read_json(self.d/'corpus'/'P0.json')
        local=pipe.snippet_candidates(src)
        first=local['method'][0]
        payload={'method':[{'passage_id':first['passage_id'], 'quote':first['quote'],
                            'claim':'合成方法候选'}]}
        with patch.object(pipe,'llm_call',return_value=payload):
            self.extract(0,provider='llm',model='mock-model',allow_external=True)
        saved=pipe.read_json(self.d/'extracts'/'P0.json')
        self.assertEqual(saved['mode'],'llm_candidates_unreviewed')
        self.assertEqual(saved['entries']['method'][0]['review_status'],'unchecked')

    def test_llm_external_requires_consent(self):
        with self.assertRaisesRegex(ValueError,'allow-external'):
            pipe.llm_call(Args(allow_external=False,api_key_env='OPENAI_API_KEY',model='example',
                base_url='https://api.openai.com/v1',allow_http=False,timeout=1),'sys','prompt')

if __name__=='__main__': unittest.main()