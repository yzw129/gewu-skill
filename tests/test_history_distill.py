"""Synthetic tests only; historical project materials remain private."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "skills" / "gewu" / "scripts"))
from gewu_history_distill import import_cards


class ImportHistoryTests(unittest.TestCase):
    def fixture(self):
        return {"rules":[{
            "id":"SYN-01","status":"candidate","success_outcome":"not_verified",
            "domain":"research","trigger":"synthetic event",
            "action":"synthetic experiment","rationale":"synthetic reason",
            "limits":"synthetic limitation","verification_check":"synthetic check",
            "source_task_ids":["TRAIN-01"]
        }]}
    def test_import_is_unverified(self):
        result=import_cards(self.fixture())
        x=result["experiences"][0]
        self.assertEqual(x["status"],"candidate")
        self.assertEqual(x["verification"]["verdict"],"pending")
        self.assertIsNone(x["verification"]["reviewer_id"])
    def test_cannot_leak_holdout(self):
        with self.assertRaisesRegex(ValueError,"泄漏"):
            import_cards(self.fixture(),["TRAIN-01"])
    def test_cannot_import_approved_without_review(self):
        src=self.fixture();src["rules"][0]["status"]="verified"
        with self.assertRaisesRegex(ValueError,"非候选"):
            import_cards(src)
    def test_cannot_fake_success(self):
        src=self.fixture();src["rules"][0]["success_outcome"]="success"
        with self.assertRaisesRegex(ValueError,"非候选"):
            import_cards(src)
    def test_requires_evidence_origin(self):
        src=self.fixture();src["rules"][0]["source_task_ids"]=[]
        with self.assertRaisesRegex(ValueError,"来源任务"):
            import_cards(src)
    def test_duplicate_rejected(self):
        src=self.fixture();src["rules"].append(dict(src["rules"][0]))
        with self.assertRaisesRegex(ValueError,"重复"):
            import_cards(src)


if __name__=="__main__":
    unittest.main()
