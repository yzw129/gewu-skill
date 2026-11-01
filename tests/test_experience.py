"""Structural tests use synthetic traces, NOT historical real research executions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"skills"/"gewu"/"scripts"))
import gewu_experience as e

class TestExperienceFeedback(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.skill=self.root/"skill.md";self.skill.write_text("Synthetic shared base skill.",encoding="utf8")
        self.tasks=[{"task_id":f"T{i:02}","origin_skill":"https://example.invalid/skill",
                     "original_request":f"Historical example {i}",
                     "task_type":"research","prompt":f"Task {i}",
                     "context":"Synthetic context","tags":["research"],
                     "expected_artifact":"research plan",
                     "external_success_criteria":"external reviewer approves validity",
                     "historical_input_ref":f"fixture/input{i}.json",
                     "historical_output_ref":f"fixture/output{i}.json"} for i in range(1,11)]
        self.p={"schema_version":e.SCHEMA,"model":"mock","base_url":"https://example.invalid",
                "base_skill_file":str(self.skill),"max_revisions":2,
                "input_usd_per_million":1.0,"output_usd_per_million":2.0,
                "cost_limit_usd":1.0,
                "success_rule":"external_human_binary_verdict",
                "change_policy":"freeze_before_both_arms"}
        self.exp={"schema_version":e.SCHEMA,"experiences":[{
            "id":"E001","status":"verified","tags":["research"],
            "trigger":"Research task","action":"Run a control experiment",
            "reason":"Synthetic instruction","limits":"only for test",
            "verification_check":"Compare baseline and treatment",
            "source_task_ids":["D000"],
            "verification":{"verdict":"approved","reviewer_id":"reviewer-1",
                             "evidence_ref":"synthetic-review.txt",
                             "verified_at":"2026-11-01"}}]}
        e.save(self.root/"tasks.json",{"schema_version":e.SCHEMA,"tasks":self.tasks})
        e.save(self.root/"protocol.json",self.p)
        e.save(self.root/"experiences.json",self.exp)
        e.cmd_freeze(SimpleNamespace(project=self.root))
        self.lock=e.load(self.root/"freeze.lock.json")
    def make_runs(self,good=True):
        runs=[]
        for t in self.tasks:
            for arm in e.ARMS:
                mem=e.selected_memory(e.validated_experiences(self.exp,self.tasks),t) if arm=="verified_memory" else []
                success=(arm=="verified_memory") if good else True
                usage={"prompt_tokens":100 if arm=="verified_memory" else 1000,
                       "completion_tokens":100}
                runs.append({"schema_version":e.SCHEMA,"task_id":t["task_id"],"arm":arm,
                             "lock_sha256":e.sha(self.lock),"task_sha256":e.sha(t),
                             "prompt_sha256":e.sha(e.prompt_for(t,arm,self.skill.read_text(),mem)),
                             "memory_ids":[x["id"] for x in mem],"model":"mock",
                             "attempts":[{"number":1,"response":"synthetic",
                                          "usage":usage,"cost_estimate_usd":e.estimated_cost(usage,self.p),
                                          "review":{"success":success,"reviewer_id":"reviewer-1",
                                                    "evidence_ref":"synthetic-audit","feedback":"synthetic"}}]})
        return runs
    def test_freeze_and_valid_memory(self):
        self.assertEqual(len(e.frozen(self.root)[0]),10)
        self.assertEqual(len(e.frozen(self.root)[2]),1)
    def test_requires_ten_cases(self):
        s=e.load(self.root/"tasks.json");s["tasks"].pop()
        with self.assertRaisesRegex(ValueError,"10个"): e.validate_suite(s)
    def test_freeze_changes_rejected(self):
        s=e.load(self.root/"tasks.json")
        s["tasks"][0]["prompt"]="tampered"
        e.save(self.root/"tasks.json",s,overwrite=True)
        with self.assertRaisesRegex(ValueError,"冻结后"):e.frozen(self.root)
    def test_unverified_memory_is_not_selected(self):
        mem=copy.deepcopy(self.exp)
        mem["experiences"][0]["status"]="candidate"
        self.assertEqual(e.validated_experiences(mem,self.tasks),[])
    def test_memory_leakage_rejected(self):
        mem=copy.deepcopy(self.exp)
        mem["experiences"][0]["source_task_ids"]=["T01"]
        with self.assertRaisesRegex(ValueError,"泄漏"):e.validated_experiences(mem,self.tasks)
    def test_external_review_required(self):
        mem=copy.deepcopy(self.exp)
        mem["experiences"][0]["verification"]["reviewer_id"]="model"
        with self.assertRaisesRegex(ValueError,"核验人员"):e.validated_experiences(mem,self.tasks)
    def test_memory_arm_has_only_verified_notes(self):
        task=self.tasks[0]
        good=e.prompt_for(task,"verified_memory","same",e.validated_experiences(self.exp,self.tasks))
        base=e.prompt_for(task,"no_memory","same",[])
        self.assertIn("E001",good);self.assertNotIn("E001",base)
    def test_report_rejects_missing_human_judgment(self):
        runs=self.make_runs();runs[0]["attempts"][0]["review"]=None
        with self.assertRaisesRegex(ValueError,"独立外部"):e.evaluate(runs,self.tasks,self.p,self.lock,e.validated_experiences(self.exp,self.tasks),self.skill.read_text())
    def test_report_rejects_missing_cost(self):
        runs=self.make_runs();runs[0]["attempts"][0]["usage"]={}
        with self.assertRaisesRegex(ValueError,"token"):e.evaluate(runs,self.tasks,self.p,self.lock,e.validated_experiences(self.exp,self.tasks),self.skill.read_text())
    def test_favorable_pilot_condition(self):
        r=e.evaluate(self.make_runs(),self.tasks,self.p,self.lock,e.validated_experiences(self.exp,self.tasks),self.skill.read_text())
        self.assertEqual(r["metrics"]["verified_memory"]["success_rate"],1)
        self.assertEqual(r["metrics"]["no_memory"]["success_rate"],0)
        self.assertTrue(r["externally_reported_pilot_improvement"])
    def test_sole_cost_increase_blocks_promotion(self):
        runs=self.make_runs()
        for run in runs:
            if run["arm"]=="verified_memory":
                run["attempts"][0]["usage"]={"prompt_tokens":10000,"completion_tokens":100}
                run["attempts"][0]["cost_estimate_usd"]=e.estimated_cost(run["attempts"][0]["usage"],self.p)
        r=e.evaluate(runs,self.tasks,self.p,self.lock,e.validated_experiences(self.exp,self.tasks),self.skill.read_text())
        self.assertFalse(r["externally_reported_pilot_improvement"])
    def test_success_cannot_be_revised(self):
        runs=self.make_runs(good=False)
        a=runs[0]
        a["attempts"].append(dict(a["attempts"][0],number=2))
        with self.assertRaisesRegex(ValueError,"成功后"):e.evaluate(runs,self.tasks,self.p,self.lock,e.validated_experiences(self.exp,self.tasks),self.skill.read_text())
    def test_no_real_model_without_opt_in(self):
        with self.assertRaisesRegex(ValueError,"--allow-external"):
            e.cmd_run(SimpleNamespace(project=self.root,task="T01",arm="no_memory",allow_external=False))
    def test_external_feedback_required_for_failure(self):
        p=self.root/"runs"/"T01.no_memory.json"
        e.save(p,{"schema_version":e.SCHEMA,"lock_sha256":e.sha(self.lock),"task_id":"T01",
                  "arm":"no_memory","attempts":[{"number":1,"response":"synthetic","review":None}]})
        with self.assertRaisesRegex(ValueError,"修订反馈"):
            e.cmd_judge(SimpleNamespace(project=self.root,run=p,success=False,
                              reviewer="researcher-1",evidence_ref="trace",feedback=""))
if __name__=="__main__":unittest.main()
