"""Purely synthetic tests for evidence-matched evaluation (never scientific findings)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/gewu/scripts"))
import gewu_v04 as old
import gewu_eval_v041 as three


class ThreeArmEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d = Path(self.temp.name)
        old.dump(self.d/"project.json", {"evaluation": {"holdout_ids": ["T-paper"]}})
        bench = {
          "schema_version": "0.4", "rubric": old.RUBRIC,
          "tasks": [
            {"task_id": "dev1", "split": "dev", "question": "合成题：如何设计对照？",
             "context": "此资料完全虚构", "source_paper_ids": []},
            {"task_id": "test1", "split": "test", "question": "合成未见题：如何处理反例？",
             "context": "此资料完全虚构", "source_paper_ids": ["T-paper"]}
          ]
        }
        old.dump(old.bench_path(self.d), bench)
        old.dump(self.d/"evaluation/benchmark.lock.json",{
            "schema_version": "0.4","benchmark_sha256":old.digest(bench)})
        (self.d/"evidence.md").write_text("SYNTHETIC research evidence",encoding="utf8")
        (self.d/"SKILL.md").write_text("SYNTHETIC IF THEN BECAUSE EXCEPT",encoding="utf8")

    def dummy(self, arm, split="dev", evidence=True):
        return {
          "schema_version": "0.4.1", "arm": arm, "split": split,
          "model": "fake", "base_url": "https://notreal.invalid",
          "temperature": 0, "benchmark_sha256": old.digest(old.load(old.bench_path(self.d))),
          "evidence_sha256": old.digest("SYNTHETIC research evidence") if arm != "baseline" and evidence else None,
          "skill_sha256": old.digest("SYNTHETIC IF THEN BECAUSE EXCEPT") if arm == "skill" else None,
          "answers": [{"task_id": "dev1" if split=="dev" else "test1",
                       "response": "合成模型回答，非真实调用"}]
        }

    def test_three_conditions_are_different(self):
        ev = "same evidence"
        a = three.system_prompt("baseline", "", "")
        b = three.system_prompt("retrieval", ev, "")
        c = three.system_prompt("skill", ev, "method")
        self.assertNotIn(ev, a)
        self.assertIn(ev,b); self.assertIn(ev,c)
        self.assertNotIn("method",b); self.assertIn("method",c)

    def test_evidence_mismatch_rejected(self):
        runs={arm:self.dummy(arm) for arm in three.ARMS}
        runs["skill"]["evidence_sha256"]=old.digest("different")
        with self.assertRaisesRegex(ValueError,"不一致"):
            three.checked_runs(self.d,runs)

    def test_missing_evidence_rejected(self):
        runs={arm:self.dummy(arm) for arm in three.ARMS}
        runs["retrieval"]["evidence_sha256"]=None
        with self.assertRaisesRegex(ValueError,"不一致"):
            three.checked_runs(self.d,runs)

    def test_model_mismatch_rejected(self):
        runs={arm:self.dummy(arm) for arm in three.ARMS}
        runs["skill"]["model"]="different-model"
        with self.assertRaisesRegex(ValueError,"运行条件不一致"):
            three.checked_runs(self.d,runs)

    def test_task_leakage_from_split_rejected(self):
        runs={arm:self.dummy(arm) for arm in three.ARMS}
        runs["retrieval"]["answers"][0]["task_id"]="test1"
        with self.assertRaisesRegex(ValueError,"缺漏"):
            three.checked_runs(self.d,runs)

    def test_requires_real_user_opt_in(self):
        args=SimpleNamespace(project=self.d,arm="baseline",split="dev",
                             evidence_pack=None,skill=None,output=self.d/"run.json",
                             allow_external=False)
        with self.assertRaisesRegex(ValueError,"显式"):
            three.cmd_run(args)

    def test_runs_with_mock_model_only(self):
        path=self.d/"run.json"
        args=SimpleNamespace(project=self.d,arm="retrieval",split="dev",
                             evidence_pack=self.d/"evidence.md",skill=None,
                             output=path,allow_external=True,model="fake",
                             base_url="https://notreal.invalid")
        with patch.object(three.core,"model_call",return_value="SIMULATED") as call:
            three.cmd_run(args)
        self.assertEqual(call.call_count,1)
        self.assertEqual(old.load(path)["evidence_sha256"],old.digest("SYNTHETIC research evidence"))
        self.assertEqual(old.load(path)["answers"][0]["response"],"SIMULATED")

    def test_blind_score_all_three(self):
        paths={}
        for arm in three.ARMS:
            path=self.d/f"{arm}.json"
            old.dump(path,self.dummy(arm))
            paths[arm]=path
        packet=self.d/"blind.json"; mapping=self.d/"mapping.json"
        three.cmd_blind(SimpleNamespace(project=self.d,packet=packet,mapping=mapping,**paths))
        cases=old.load(packet)["cases"]
        self.assertEqual(len(cases),3)
        self.assertNotIn('"arm"',json.dumps(cases,ensure_ascii=False))
        original=old.load(mapping)["mapping"]
        vals={"baseline":2,"retrieval":3,"skill":4}
        grades=self.d/"grades.json"
        old.dump(grades,{"grades":[{"case_id":cid,"reviewer":"synthetic-test-only",
                                     "scores":{key:vals[item["arm"]] for key in old.RUBRIC}}
                                    for cid,item in original.items()]})
        out=self.d/"report.json"
        three.cmd_score(SimpleNamespace(packet=packet,mapping=mapping,grades=grades,output=out))
        report=old.load(out)
        self.assertEqual(report["task_count"],1)
        self.assertEqual(report["mean_deltas"]["skill_minus_retrieval"]["experiment"],1)

    def test_score_requires_reviewed_completeness(self):
        packet=self.d/"p.json"; mapping=self.d/"m.json"; grades=self.d/"g.json"
        old.dump(packet,{"schema_version":"0.4.1","split":"dev","rubric":old.RUBRIC,
                         "cases":[{"case_id":"1","task_id":"dev1","response":"fake"}]})
        old.dump(mapping,{"schema_version":"0.4.1","split":"dev","mapping":{
                  "1":{"task_id":"dev1","arm":"baseline"}}})
        old.dump(grades,{"grades":[]})
        with self.assertRaisesRegex(ValueError,"尚未覆盖"):
            three.cmd_score(SimpleNamespace(packet=packet,mapping=mapping,
                                            grades=grades,output=self.d/"out.json"))


if __name__=="__main__":
    unittest.main()
