"""Gewu v0.5 synthetic capability contract tests; no real source or model evidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/gewu/scripts"))
import gewu_capabilities as c


class TestCapability(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.d = self.base / "writing"
        c.cmd_init(SimpleNamespace(directory=self.d, id="paper-writing", domain="writing"))

    def setup_reviewed(self):
        data = c.read(self.d / "capability.json")
        data["sources"] = [{"id": "src-1", "kind": "guideline",
                            "title": "SYNTHETIC guideline for testing",
                            "location": "local synthetic", "locator": "line 1",
                            "reviewed": True, "usage_rights": "self-made synthetic content"}]
        data["rules"] = [{"id": "W01", "status": "reviewed",
                          "trigger": "需要表达实验证据", "action": "先写核心发现再列证据",
                          "why": "SYNTHETIC ONLY", "exceptions": "无实际研究证据",
                          "verification": "人工核对事实与方法一致性",
                          "source_ids": ["src-1"]}]
        c.write(self.d / "capability.json", data)
        ev = c.read(self.d / "evaluation.json")
        ev["scenarios"][0]["prompt"] = "开发集：检查一句话的论证结构"
        ev["scenarios"][1]["prompt"] = "测试集：核验一段正文的引用一致性"
        c.write(self.d / "evaluation.json", ev)

    def test_all_four_domains_available(self):
        self.assertEqual(set(c.DOMAINS), {"research", "writing", "visualization", "presentation"})
        self.assertNotEqual(c.DOMAINS["writing"]["metrics"], c.DOMAINS["visualization"]["metrics"])

    def test_new_template_is_not_approved(self):
        errors, warnings, _, _ = c.validate(self.d)
        self.assertEqual(errors, [])
        self.assertTrue(any("没有已审查规则" in x for x in warnings))
        with self.assertRaises(ValueError):
            c.cmd_compile(SimpleNamespace(directory=self.d,output=self.base/"output",preview=False))

    def test_reviewed_rule_can_compile_after_freeze(self):
        self.setup_reviewed()
        c.cmd_freeze(SimpleNamespace(directory=self.d))
        dest = self.base / "skill"
        c.cmd_compile(SimpleNamespace(directory=self.d, output=dest,preview=False))
        txt = (dest/"SKILL.md").read_text()
        self.assertIn("先写核心发现",txt)
        self.assertIn("PROVISIONAL",txt)
        self.assertEqual(c.read(dest/"manifest.json")["review_status"], "reviewed_rules_not_behaviorally_tested")

    def test_unreviewed_source_rejected(self):
        self.setup_reviewed()
        r = c.read(self.d/"capability.json")
        r["sources"][0]["reviewed"] = False
        c.write(self.d/"capability.json",r)
        errors, _, _, _ = c.validate(self.d)
        self.assertTrue(any("未审查来源" in e for e in errors))

    def test_candidate_can_only_preview(self):
        self.setup_reviewed()
        r = c.read(self.d/"capability.json")
        r["rules"][0]["status"]="candidate"
        c.write(self.d/"capability.json",r)
        with self.assertRaises(ValueError):
            c.cmd_compile(SimpleNamespace(directory=self.d,output=self.base/"formal",preview=False))
        c.cmd_compile(SimpleNamespace(directory=self.d,output=self.base/"preview",preview=True))
        self.assertIn("DRAFT", (self.base/"preview"/"SKILL.md").read_text())

    def test_freeze_detects_modified_evaluation(self):
        self.setup_reviewed()
        c.cmd_freeze(SimpleNamespace(directory=self.d))
        e = c.read(self.d/"evaluation.json")
        e["scenarios"][1]["prompt"]="替换了题目"
        c.write(self.d/"evaluation.json", e)
        errors, _, _, _ = c.validate(self.d)
        self.assertTrue(any("内容被修改" in x for x in errors))

    def test_holdout_source_leakage_rejected(self):
        self.setup_reviewed()
        e = c.read(self.d/"evaluation.json")
        e["scenarios"][1]["source_ids"]=["src-1"]
        c.write(self.d/"evaluation.json", e)
        errors, _, _, _ = c.validate(self.d)
        self.assertTrue(any("泄漏" in x for x in errors))

    def test_invalid_artifact_scoring_rejected(self):
        self.setup_reviewed()
        e = c.read(self.d/"evaluation.json")
        e["rubric"] = ["pretty"]
        c.write(self.d/"evaluation.json", e)
        errors, _, _, _ = c.validate(self.d)
        self.assertTrue(any("评价维度" in x for x in errors))

    def test_duplicate_rule_id_detected(self):
        self.setup_reviewed()
        r = c.read(self.d/"capability.json")
        r["rules"].append(dict(r["rules"][0]))
        c.write(self.d/"capability.json",r)
        errors, _, _, _ = c.validate(self.d)
        self.assertTrue(any("规则 ID 缺失或重复" in x for x in errors))

    def test_no_bypass_with_missing_rule_evidence(self):
        self.setup_reviewed()
        r = c.read(self.d/"capability.json")
        r["rules"][0]["source_ids"]=["unknown"]
        c.write(self.d/"capability.json",r)
        errors, _, _, _ = c.validate(self.d)
        self.assertTrue(any("未知来源" in x for x in errors))

    def test_visualization_checks_include_fidelity(self):
        self.assertIn("data_fidelity", c.DOMAINS["visualization"]["metrics"])
        self.assertTrue(any("数据图" in x for x in c.DOMAINS["visualization"]["checks"]))

    def test_no_overwrite(self):
        with self.assertRaisesRegex(ValueError,"拒绝覆盖"):
            c.cmd_init(SimpleNamespace(directory=self.d,id="other-id",domain="writing"))


if __name__=="__main__":
    unittest.main()
