"""Gewu v0.4 synthetic integration tests, no genuine papers and no network calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "skills" / "gewu" / "scripts"))
import gewu
import gewu_v04 as v


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.d = self.root / "project"
        gewu.cmd_init(SimpleNamespace(directory=str(self.d), topic="合成科研课题",
            scope="用于软件单元测试；没有任何真实科学论据", project_id="synthetic"))
        p = v.load(self.d / "project.json")
        p["protocol"].update(sources=["synthetic"], queries=["fake"],
                             inclusion=["fake"], exclusion=["other"])
        v.dump(self.d / "project.json", p)
        self.paper("P1", "synthesis")
        self.paper("P2", "holdout")
        p = v.load(self.d / "project.json")
        p["evaluation"]["holdout_ids"] = ["P2"]
        v.dump(self.d / "project.json", p)
        gewu.cmd_freeze(SimpleNamespace(directory=str(self.d), part="protocol"))
        gewu.cmd_freeze(SimpleNamespace(directory=str(self.d), part="evaluation"))
        self.checked_rule()
        v.cmd_init_bench(SimpleNamespace(project=self.d))
        b = v.load(v.bench_path(self.d))
        b["tasks"] = [
            {"task_id": "D1", "split": "dev", "question": "合成任务：如何验证 A?",
             "context": "Synthetic input, no real paper.", "source_paper_ids": []},
            {"task_id": "T1", "split": "test", "question": "合成未见任务：如何对照 B?",
             "context": "Synthetic input.", "source_paper_ids": ["P2"]}
        ]
        v.dump(v.bench_path(self.d), b)
        v.cmd_freeze_bench(SimpleNamespace(project=self.d))
        self.skilldir = self.root / "skill"
        v.cmd_build(SimpleNamespace(project=self.d, output=self.skilldir))

    def paper(self, pid, pool):
        papers = v.load(self.d / "papers.json")
        papers.append({"paper_id": pid, "title": f"[SYNTHETIC] {pid}",
            "access_level": "fulltext", "pool": pool,
            "screening": {"decision": "included", "reason": "synthetic"},
            "url": f"https://example.invalid/{pid}"})
        v.dump(self.d / "papers.json", papers)

    def checked_rule(self):
        rules = [{
            "rule_id": "R001", "question": "如何验证", "statement": "使用对照",
            "condition": "资料不足", "action": "明确假设与对照",
            "rationale": "合成假设，不构成真实科研结论",
            "limits": "仅合成测试", "kind": "recommendation", "status": "reviewed",
            "evidence": [{"paper_id": "P1", "locator": "Methods 1", "summary": "SYNTHETIC",
                          "source_part": "methods", "review_status": "checked"}],
            "counterexamples": [], "counterexample_search": {
                "status": "searched", "notes": "synthetic"}
        }]
        v.dump(self.d / "rules.json", rules)

    def runs(self, split="dev"):
        b = v.load(v.bench_path(self.d))
        sha = v.digest(b)
        a = {"schema_version": "0.4", "arm": "baseline", "split": split,
             "model": "mock", "base_url": "https://example.invalid",
             "temperature": 0, "benchmark_sha256": sha,
             "skill_sha256": None, "answers": [{"task_id": "D1" if split == "dev" else "T1",
                                                "response": "synthetic base answer"}]}
        s = dict(a)
        s["arm"] = "skill"
        s["answers"] = [{"task_id": a["answers"][0]["task_id"], "response": "synthetic skill answer"}]
        s["skill_sha256"] = v.digest((self.skilldir / "SKILL.md").read_text())
        return a, s

    def test_skill_build_has_executable_rules(self):
        text = (self.skilldir / "SKILL.md").read_text()
        self.assertIn("触发条件 IF", text)
        self.assertIn("执行动作 THEN", text)
        self.assertIn("机制与可辨识性", text)
        self.assertIn("R001", text)
        self.assertNotIn("P2@", text)

    def test_unchecked_rule_blocks_build(self):
        rs = v.load(self.d / "rules.json")
        rs[0]["evidence"][0]["review_status"] = "unchecked"
        v.dump(self.d / "rules.json", rs)
        with self.assertRaises(ValueError):
            v.reviewed_rules(self.d)

    def test_modified_benchmark_rejected(self):
        b = v.load(v.bench_path(self.d))
        b["tasks"][1]["question"] = "悄悄更换测试题"
        v.dump(v.bench_path(self.d), b)
        with self.assertRaisesRegex(ValueError, "已被修改"):
            v.frozen_bench(self.d)

    def test_dev_cannot_use_holdout_source(self):
        b = v.load(v.bench_path(self.d))
        b["tasks"][0]["source_paper_ids"] = ["P2"]
        with self.assertRaisesRegex(ValueError, "不能引用预留论文"):
            v.validate_bench(self.d, b)

    def test_test_cannot_use_training_source(self):
        b = v.load(v.bench_path(self.d))
        b["tasks"][1]["source_paper_ids"] = ["P1"]
        with self.assertRaisesRegex(ValueError, "非预留论文"):
            v.validate_bench(self.d, b)

    def test_model_runs_need_opt_in(self):
        args = SimpleNamespace(project=self.d, arm="baseline", split="dev", skill=None,
               output=self.root / "run.json", allow_external=False, model="mock",
               base_url="https://example.invalid")
        with self.assertRaisesRegex(ValueError, "授权"):
            v.cmd_run(args)

    def test_real_run_with_mocked_provider(self):
        args = SimpleNamespace(project=self.d, arm="skill", split="dev",
               skill=str(self.skilldir / "SKILL.md"), output=self.root / "run.json",
               allow_external=True, model="mock", base_url="https://example.invalid")
        with patch.object(v, "model_call", return_value="MOCK ANSWER") as mock:
            v.cmd_run(args)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(v.load(args.output)["answers"][0]["response"], "MOCK ANSWER")

    def blind_score(self, split="dev", skill_score=2):
        a, s = self.runs(split)
        ap, sp = self.root / (split+"_baseline.json"), self.root / (split+"_skill.json")
        v.dump(ap, a); v.dump(sp, s)
        packet = self.root / (split+"_blind.json")
        secret = self.root / (split+"_mapping.json")
        v.cmd_blind(SimpleNamespace(project=self.d, baseline=ap, skill=sp,
                                   packet=packet, mapping=secret))
        m = v.load(secret)
        grades = []
        for case_id, info in m["mapping"].items():
            score = 3 if info["arm"] == "baseline" else skill_score
            grades.append({"case_id": case_id, "reviewer": "synthetic-reviewer",
                           "scores": {key: score for key in v.RUBRIC}})
        gpath = self.root / (split+"_grades.json")
        v.dump(gpath, {"grades": grades})
        report = self.root / (split+"_report.json")
        v.cmd_score(SimpleNamespace(packet=packet, mapping=secret, grades=gpath, output=report))
        return report

    def test_blinding_hides_arm_and_scores_paired(self):
        report = self.blind_score(skill_score=2)
        result = v.load(report)
        self.assertEqual(result["skill_losses"], 1)
        self.assertEqual(result["mean_delta"]["experiment"], -1)
        packet = v.load(self.root / "dev_blind.json")
        self.assertNotIn('"arm"', json.dumps(packet))

    def test_incomplete_grades_rejected(self):
        self.blind_score()
        packet = self.root / "dev_blind.json"
        secret = self.root / "dev_mapping.json"
        gpath = self.root / "empty.json"
        v.dump(gpath, {"grades": []})
        with self.assertRaisesRegex(ValueError, "未覆盖"):
            v.cmd_score(SimpleNamespace(packet=packet, mapping=secret, grades=gpath,
                                        output=self.root / "empty_report.json"))

    def test_evolve_rejects_test_report(self):
        report = self.blind_score("test")
        revision = self.root / "revision.json"
        v.dump(revision, {"changes": [{"failure_task_ids": ["T1"], "trigger": "遇到T",
              "new_action": "检查对照", "rationale": "test leakage"}]})
        with self.assertRaisesRegex(ValueError, "禁止测试集反馈"):
            v.cmd_evolve(SimpleNamespace(project=self.d, base_skill=self.skilldir/"SKILL.md",
                            dev_report=report, revision=revision, output=self.root/"candidate"))

    def test_evolution_creates_unapproved_candidate(self):
        report = self.blind_score("dev")
        revision = self.root / "revision.json"
        v.dump(revision, {"changes": [{"failure_task_ids": ["D1"], "trigger": "出现不可靠实验",
              "new_action": "明确失败判据", "rationale": "dev feedback"}]})
        out = self.root / "candidate"
        v.cmd_evolve(SimpleNamespace(project=self.d, base_skill=self.skilldir/"SKILL.md",
                        dev_report=report, revision=revision, output=out))
        self.assertIn("失败判据", (out/"SKILL.md").read_text())
        self.assertEqual(v.load(out/"manifest.json")["promotion_status"], "NOT_APPROVED")

    def test_evolution_requires_actual_failure(self):
        report = self.blind_score("dev", skill_score=5)
        revision = self.root / "revision.json"
        v.dump(revision, {"changes": [{"failure_task_ids": ["D1"], "trigger": "t",
              "new_action": "a", "rationale": "r"}]})
        with self.assertRaisesRegex(ValueError, "没有改善"):
            v.cmd_evolve(SimpleNamespace(project=self.d, base_skill=self.skilldir/"SKILL.md",
                            dev_report=report, revision=revision, output=self.root/"candidate"))


if __name__ == "__main__":
    unittest.main()
