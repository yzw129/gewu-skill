"""Synthetic archive audit tests — cannot establish real scholarly success."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/gewu/scripts"))
import gewu_history_preflight as pilot


class HistoricalPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        source = root/"sample.docx"
        with zipfile.ZipFile(source,"w") as f:
            f.writestr("word/document.xml","<document>synthetic content</document>")
        digest = pilot.digest_file(source)
        self.tasks = [{
           "task_id": f"H{i:02}", "historical_inputs":[{"local_path":str(source),"sha256":digest}],
           "historical_outputs":[{"local_path":str(source),"sha256":digest}],
           "original_prompt_transcript":"Exact synthetic request",
           "prompt_source_ref":"local-fixture"} for i in range(1,11)]
    def test_complete_synthetic_registry(self):
        out, code = pilot.evaluate({"tasks":self.tasks},True)
        self.assertEqual(out["verified_file_count"],20)
        self.assertEqual(out["fully_replayable_count"],10)
        self.assertEqual(code,0)
        self.assertFalse(out["can_claim_real_success_gain"])
    def test_missing_historical_prompt_is_blocked(self):
        self.tasks[0]["original_prompt_transcript"]="not_recovered"
        report,code=pilot.evaluate({"tasks":self.tasks},True)
        self.assertEqual(report["fully_replayable_count"],9)
        self.assertEqual(code,2)
    def test_missing_original_source_ref_is_blocked(self):
        self.tasks[3]["prompt_source_ref"]=None
        report,code=pilot.evaluate({"tasks":self.tasks},True)
        self.assertEqual(report["fully_replayable_count"],9)
        self.assertEqual(code,2)
    def test_wrong_hash_is_blocked(self):
        self.tasks[2]["historical_outputs"][0]["sha256"]="0"*64
        report,code=pilot.evaluate({"tasks":self.tasks},True)
        self.assertEqual(report["fully_replayable_count"],9)
    def test_missing_original_file_is_blocked(self):
        self.tasks[1]["historical_inputs"][0]["local_path"]="/nonexistent-gewu-file"
        report,code=pilot.evaluate({"tasks":self.tasks},True)
        self.assertEqual(report["fully_replayable_count"],9)
    def test_duplicate_id_rejected(self):
        self.tasks[1]["task_id"]=self.tasks[0]["task_id"]
        with self.assertRaisesRegex(ValueError,"重复"):
            pilot.evaluate({"tasks":self.tasks})
    def test_not_exactly_ten_rejected(self):
        with self.assertRaisesRegex(ValueError,"十个"):
            pilot.evaluate({"tasks":self.tasks[:-1]})
    def test_disallows_corrupt_office_archive(self):
        p=Path(self.temp.name)/"bad.docx"
        p.write_bytes(b"not a real zip")
        self.tasks[0]["historical_inputs"][0]={"local_path":str(p),"sha256":pilot.digest_file(p)}
        out,code=pilot.evaluate({"tasks":self.tasks},True)
        self.assertEqual(out["fully_replayable_count"],9)


if __name__=="__main__":
    unittest.main()
