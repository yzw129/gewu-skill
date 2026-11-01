#!/usr/bin/env python3
"""Gewu experience feedback pilot (v0.4-EXP1).

The memory arm differs from no-memory only by manually externally verified
experience notes. Ten historical tasks are required, with the same frozen model,
base skill and source inputs. Every attempt must receive an external human verdict
before revision or scoring. This is not LLM training and cannot self-certify skill.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="0.4-exp1"
ARMS=("no_memory","verified_memory")
METRICS=("success_rate","mean_revisions","mean_estimated_model_cost_usd")
UNVERIFIED={"candidate","rejected"}
REVIEW_BAN={"model","llm","agent","automatic","self","auto","gpt"}

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def stable(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"))

def sha(x):
    return hashlib.sha256((x if isinstance(x,bytes) else stable(x).encode("utf8"))).hexdigest()

def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf8"))
    except (OSError,json.JSONDecodeError) as e:
        raise ValueError(f"无法读取 {path}: {e}") from e

def save(path,data,overwrite=False):
    p=Path(path)
    if p.exists() and not overwrite:
        raise ValueError(f"拒绝覆盖已有记录: {p}")
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    temp.replace(p)

def nonempty(x):
    return isinstance(x,str) and bool(x.strip())

def reviewer_valid(v):
    return (nonempty(v) and v.strip().lower() not in REVIEW_BAN
            and len(v.strip())>=3)

def validate_suite(suite):
    if suite.get("schema_version")!=SCHEMA:
        raise ValueError("任务集版本错误")
    tasks=suite.get("tasks")
    if not isinstance(tasks,list) or len(tasks)!=10:
        raise ValueError("必须恰好选择10个历史科研任务")
    seen=set()
    for t in tasks:
        if not isinstance(t,dict): raise ValueError("任务格式错误")
        k=t.get("task_id")
        if not nonempty(k) or k in seen: raise ValueError("任务ID为空或重复")
        seen.add(k)
        for field in ("origin_skill","original_request","task_type","prompt",
                      "expected_artifact","external_success_criteria"):
            if not nonempty(t.get(field)): raise ValueError(f"{k} 缺少 {field}")
        if not isinstance(t.get("tags"),list) or not t["tags"] or any(not nonempty(z) for z in t["tags"]):
            raise ValueError(f"{k} 缺少任务标签")
        for field in ("historical_input_ref","historical_output_ref"):
            if not nonempty(t.get(field)):
                raise ValueError(f"{k} 未提供原始历史输入/输出记录 {field}；不可声称完成历史回放")
        if not isinstance(t.get("context"),str): raise ValueError(f"{k} 的 context 应为字符串")
    return tasks

def validate_protocol(p):
    if p.get("schema_version")!=SCHEMA: raise ValueError("协议版本错误")
    for f in ("model","base_url","base_skill_file"):
        if not nonempty(p.get(f)): raise ValueError(f"协议缺少 {f}")
    for f in ("input_usd_per_million","output_usd_per_million","cost_limit_usd"):
        n=p.get(f)
        if type(n) not in (int,float) or not (0<=n<100000):
            raise ValueError(f"{f} 必须是非负、有限的有限量纲费率/预算")
    revisions=p.get("max_revisions")
    if type(revisions) is not int or not 0<=revisions<=10:
        raise ValueError("max_revisions 必须为0-10整数")
    if p.get("success_rule")!="external_human_binary_verdict":
        raise ValueError("成功必须来自外部人工二值判断")
    if p.get("change_policy")!="freeze_before_both_arms":
        raise ValueError("先冻结任务与指标，禁止调换协议")
    return p

def validated_experiences(memory,suite_tasks):
    if memory.get("schema_version")!=SCHEMA: raise ValueError("经验库版本错误")
    exp=memory.get("experiences")
    if not isinstance(exp,list): raise ValueError("经验库必须是数组")
    ids=set(); tasks={t["task_id"] for t in suite_tasks}; approved=[]
    for e in exp:
        if not isinstance(e,dict): raise ValueError("经验条目格式错误")
        k=e.get("id")
        if not nonempty(k) or k in ids: raise ValueError("经验 ID 缺失或重复")
        ids.add(k)
        if e.get("status") in UNVERIFIED: continue
        if e.get("status")!="verified": raise ValueError(f"{k}: 经验状态不合法")
        for field in ("trigger","action","reason","limits","verification_check"):
            if not nonempty(e.get(field)): raise ValueError(f"{k}: {field} 为空")
        tags=e.get("tags")
        if not isinstance(tags,list) or not tags or any(not nonempty(t) for t in tags):
            raise ValueError(f"{k}: 标签无效")
        origin=e.get("source_task_ids")
        if not isinstance(origin,list) or not origin:
            raise ValueError(f"{k}: 无法追溯产生经验的历史任务")
        if set(origin)&tasks:
            raise ValueError(f"{k}: 经验来源与评估历史任务重叠，存在数据泄漏")
        v=e.get("verification")
        if not isinstance(v,dict) or v.get("verdict")!="approved":
            raise ValueError(f"{k}: 未获外部核验")
        if not reviewer_valid(v.get("reviewer_id")) or not nonempty(v.get("evidence_ref")):
            raise ValueError(f"{k}: 外部核验人员及验证证据缺失")
        if not nonempty(v.get("verified_at")):
            raise ValueError(f"{k}: 外部核验日期缺失")
        approved.append(e)
    return approved

def root_paths(root):
    r=Path(root)
    return r/"tasks.json",r/"protocol.json",r/"experiences.json",r/"freeze.lock.json"

def frozen(root):
    a,b,c,d=root_paths(root)
    tasks=validate_suite(load(a))
    protocol=validate_protocol(load(b))
    memory=load(c)
    approved=validated_experiences(memory,tasks)
    lock=load(d)
    hashes={"tasks_sha256":sha(load(a)),"protocol_sha256":sha(protocol),
            "experiences_sha256":sha(memory)}
    if any(lock.get(key)!=value for key,value in hashes.items()):
        raise ValueError("冻结后任务、协议或经验库发生变化；必须建立新的实验版本")
    skill=Path(protocol["base_skill_file"])
    if not skill.is_file():
        raise ValueError("缺少双方共同加载的基础 Skill 文件")
    base=skill.read_text(encoding="utf8")
    if sha(base)!=lock.get("base_skill_sha256"):
        raise ValueError("基础 Skill 已被修改")
    return tasks,protocol,approved,lock,base

def cmd_freeze(args):
    a,b,c,d=root_paths(args.project)
    if d.exists(): raise ValueError("已存在冻结协议，不允许覆盖")
    tasks=validate_suite(load(a));p=validate_protocol(load(b));m=load(c)
    validated_experiences(m,tasks)
    base=Path(p["base_skill_file"]).read_text(encoding="utf8")
    save(d,{"schema_version":SCHEMA,"frozen_at":now(),
            "tasks_sha256":sha(load(a)),"protocol_sha256":sha(p),
            "experiences_sha256":sha(m),"base_skill_sha256":sha(base),
            "primary":"success_rate", "secondary":["mean_revisions","mean_estimated_model_cost_usd"],
            "promotion_gate":"positive_external_success_delta_and_nonworse_secondary",
            "note":"所有指标在真实模型调用前固定；十题不足以证明普遍能力成长"})
    print("任务、经验、基础 Skill 与评估指标已冻结：10 项历史任务")
    return 0

def selected_memory(experiences,task):
    tags=set(task["tags"])
    chosen=[e for e in experiences if tags&set(e["tags"])]
    return sorted(chosen,key=lambda e:e["id"])

def prompt_for(task,arm,base,items):
    result=base+"\n\n" if base else ""
    result+="你是科研工作助手。仅根据实际输入完成任务，不编造已执行结果。"
    if arm=="verified_memory":
        if not items: raise ValueError(f"{task['task_id']}: 没有匹配该任务的已核验经验；不得伪造记忆组")
        result+="\n下面是独立审核的历史经验提示（不是事实来源或任务答案）：\n"
        for e in items:
            result+=(f"\n【{e['id']}】条件：{e['trigger']}；行动：{e['action']}；"
                     f"理由：{e['reason']}；边界：{e['limits']}；验证：{e['verification_check']}")
    return result

def ask_model(system,user,p):
    key=os.environ.get("OPENAI_API_KEY")
    if not key: raise ValueError("未配置 OPENAI_API_KEY；不提交外部模型")
    endpoint=p["base_url"].rstrip("/")+"/chat/completions"
    if not endpoint.startswith("https://"):
        raise ValueError("仅允许 HTTPS 访问模型端点")
    data=json.dumps({"model":p["model"],"temperature":0,
                     "messages":[{"role":"system","content":system},{"role":"user","content":user}]},
                    ensure_ascii=False).encode("utf8")
    req=urllib.request.Request(endpoint,data=data,
                headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=90) as response:
            result=json.loads(response.read(12000000))
        answer=result["choices"][0]["message"]["content"]
        usage=result["usage"]
        prompt=int(usage["prompt_tokens"]);completion=int(usage["completion_tokens"])
        if not isinstance(answer,str) or not answer.strip() or min(prompt,completion)<0:
            raise ValueError("空模型响应或负 token 数")
        return answer,{"prompt_tokens":prompt,"completion_tokens":completion}
    except (OSError,KeyError,ValueError,TypeError,IndexError) as exc:
        raise ValueError(f"模型请求或 token 记录失败：{exc}") from exc

def estimated_cost(tokens,p):
    return (tokens["prompt_tokens"]*p["input_usd_per_million"]+
            tokens["completion_tokens"]*p["output_usd_per_million"])/1000000.0

def cmd_run(args):
    tasks,p,experiences,lock,base=frozen(args.project)
    if not args.allow_external: raise ValueError("必须显式 --allow-external 才能向服务发送研究材料")
    task=next((t for t in tasks if t["task_id"]==args.task),None)
    if task is None: raise ValueError("任务不存在")
    mem=selected_memory(experiences,task) if args.arm=="verified_memory" else []
    system=prompt_for(task,args.arm,base,mem)
    out=Path(args.project)/"runs"/f"{args.task}.{args.arm}.json"
    if out.exists():
        record=load(out)
        if (record.get("task_sha256")!=sha(task) or record.get("prompt_sha256")!=sha(system)
                or record.get("lock_sha256")!=sha(lock) or record.get("arm")!=args.arm):
            raise ValueError("已有运行记录的任务、提示或协议不一致")
        previous=record["attempts"]
        if not previous or not previous[-1].get("review"):
            raise ValueError("上一尝试尚未经过外部评价，不能修改")
        if previous[-1]["review"]["success"]:
            raise ValueError("任务已通过外部评价，无需继续修改")
        if len(previous)>p["max_revisions"]:
            raise ValueError("已达到允许的最多修改次数")
        user=(task["prompt"]+"\n\n固定任务资料：\n"+task["context"]+
              "\n\n上一次回答：\n"+previous[-1]["response"]+
              "\n\n独立评价者要求的修订：\n"+previous[-1]["review"]["feedback"])
    else:
        record={"schema_version":SCHEMA,"task_id":task["task_id"],"arm":args.arm,
                "created_at":now(),"lock_sha256":sha(lock),"task_sha256":sha(task),
                "prompt_sha256":sha(system),"memory_ids":[e["id"] for e in mem],
                "model":p["model"],"attempts":[]}
        previous=[]
        user=task["prompt"]+"\n\n固定任务资料：\n"+task["context"]
    answer,tokens=ask_model(system,user,p)
    cost=estimated_cost(tokens,p)
    if sum(x["cost_estimate_usd"] for x in previous)+cost>p["cost_limit_usd"]:
        raise ValueError("单任务累计预算超限，拒绝写入新完成记录（可能已产生本次接口费用）")
    record["attempts"].append({"number":len(previous)+1,"at":now(),
                               "response":answer,"usage":tokens,
                               "cost_estimate_usd":cost,"review":None})
    save(out,record,overwrite=out.exists())
    print(f"已记录 {task['task_id']} / {args.arm} 第 {len(record['attempts'])} 次回答；待外部评价")
    return 0

def cmd_judge(args):
    tasks,p,experiences,lock,base=frozen(args.project)
    if not reviewer_valid(args.reviewer): raise ValueError("必须由可识别的外部人员评价，不接受 model/auto/self")
    if not nonempty(args.evidence_ref): raise ValueError("必须填写外部评价原始记录")
    path=Path(args.run)
    record=load(path)
    if record.get("schema_version")!=SCHEMA or record.get("lock_sha256")!=sha(lock):
        raise ValueError("评估记录不属于已冻结任务")
    if record.get("task_id") not in {t["task_id"] for t in tasks}:
        raise ValueError("未知历史任务")
    if record.get("arm") not in ARMS:
        raise ValueError("未知实验组")
    att=record.get("attempts",[])
    if not att or att[-1].get("review") is not None:
        raise ValueError("没有待评审的最新一次回答，禁止改动已有外部判断")
    if not args.success and not nonempty(args.feedback):
        raise ValueError("失败时必须给出可操作的修订反馈")
    att[-1]["review"]={"success":args.success,"reviewer_id":args.reviewer,
                       "evidence_ref":args.evidence_ref,
                       "feedback":args.feedback,"evaluated_at":now()}
    save(path,record,overwrite=True)
    print("已记录外部成功判定；它仅代表评分者报告，不代表程序独立验证事实")
    return 0

def evaluate(runs,tasks,protocol,lock,experiences,base):
    expected={t["task_id"]:t for t in tasks}
    results={}
    if len(runs)!=20: raise ValueError("必须有10项任务 × 2组完整运行记录")
    for run in runs:
        tid,arm=run.get("task_id"),run.get("arm")
        if tid not in expected or arm not in ARMS or (tid,arm) in results:
            raise ValueError("未知或重复任务×组")
        if run.get("schema_version")!=SCHEMA or run.get("lock_sha256")!=sha(lock):
            raise ValueError("运行记录与冻结协议不一致")
        task=expected[tid]
        mem=selected_memory(experiences,task) if arm=="verified_memory" else []
        if run.get("memory_ids")!=[e["id"] for e in mem]:
            raise ValueError("经验组未使用经过验证的匹配记忆，或无记忆组发生污染")
        if run.get("task_sha256")!=sha(task) or run.get("prompt_sha256")!=sha(prompt_for(task,arm,base,mem)):
            raise ValueError("任务输入或原始提示不一致")
        if run.get("model")!=protocol["model"]:
            raise ValueError("两组实际模型不同")
        attempts=run.get("attempts")
        if not isinstance(attempts,list) or not attempts or len(attempts)>protocol["max_revisions"]+1:
            raise ValueError("尝试次数超过预先固定预算")
        total=0.0
        for i,a in enumerate(attempts):
            if a.get("number")!=i+1 or not nonempty(a.get("response")):
                raise ValueError("缺失或重复的实际回答")
            review=a.get("review")
            if not isinstance(review,dict) or type(review.get("success")) is not bool:
                raise ValueError("每次尝试均需独立外部成功/失败判定")
            if not reviewer_valid(review.get("reviewer_id")) or not nonempty(review.get("evidence_ref")):
                raise ValueError("外部评审者或评价依据缺失")
            if i<len(attempts)-1 and review["success"]:
                raise ValueError("成功后仍继续修改，违反停止规则")
            if i<len(attempts)-1 and not nonempty(review.get("feedback")):
                raise ValueError("修改缺少独立评审反馈")
            usage=a.get("usage")
            if not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0
                    for k in ("prompt_tokens","completion_tokens")):
                raise ValueError("不能缺失或伪造 token 使用量")
            cost=estimated_cost(usage,protocol)
            if abs(cost-a.get("cost_estimate_usd",-1))>1e-9:
                raise ValueError("成本记录与冻结费率不一致")
            total+=cost
        if total>protocol["cost_limit_usd"]+1e-10:
            raise ValueError("累计成本超出冻结预算")
        results[(tid,arm)]={"success":attempts[-1]["review"]["success"],
                            "revisions":len(attempts)-1,"cost":total}
    if set(results)!={(tid,arm) for tid in expected for arm in ARMS}:
        raise ValueError("存在不完整的配对运行记录")
    table=[]
    for tid in sorted(expected):
        a,b=results[(tid,"no_memory")],results[(tid,"verified_memory")]
        table.append({"task_id":tid,"no_memory":a,"verified_memory":b,
                      "success_delta":int(b["success"])-int(a["success"]),
                      "revision_delta":b["revisions"]-a["revisions"],
                      "cost_delta_usd":round(b["cost"]-a["cost"],8)})
    stats={}
    for arm in ARMS:
        rows=[results[(tid,arm)] for tid in sorted(expected)]
        stats[arm]={"success_rate":sum(int(x["success"]) for x in rows)/10,
                    "mean_revisions":sum(x["revisions"] for x in rows)/10,
                    "mean_estimated_model_cost_usd":sum(x["cost"] for x in rows)/10,
                    "total_estimated_model_cost_usd":sum(x["cost"] for x in rows)}
    a,b=stats["no_memory"],stats["verified_memory"]
    gate=(b["success_rate"]>a["success_rate"] and
          b["mean_revisions"]<=a["mean_revisions"] and
          b["mean_estimated_model_cost_usd"]<=a["mean_estimated_model_cost_usd"])
    return {"schema_version":SCHEMA,"task_count":10,
            "metrics":stats,"pairs":table,
            "externally_reported_pilot_improvement":gate,
            "status":"external_pilot_positive_not_generalized" if gate else "no_qualified_improvement",
            "caveats":["十题仅为探索性样本，不能证明跨任务普遍提升",
                       "成功由外部人工评审记录，不保证评分者独立性或盲法",
                       "成本按token和预设价格估算，不含工具、人工及缓存差异",
                       "任务/样本无泄漏还需人工核对原始附件与来源"]}

def cmd_report(args):
    tasks,p,experiences,lock,base=frozen(args.project)
    folder=Path(args.project)/"runs"
    files=[folder/f"{t['task_id']}.{arm}.json" for t in tasks for arm in ARMS]
    runs=[load(x) for x in files]
    result=evaluate(runs,tasks,p,lock,experiences,base)
    save(args.output,result)
    print("完成10任务20组外部评估比较；状态："+result["status"])
    return 0

def main(argv=None):
    ap=argparse.ArgumentParser(description="Gewu v0.4 experience-feedback benchmark")
    sub=ap.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("freeze");a.add_argument("project");a.set_defaults(fn=cmd_freeze)
    a=sub.add_parser("run");a.add_argument("project");a.add_argument("--task",required=True)
    a.add_argument("--arm",choices=ARMS,required=True)
    a.add_argument("--allow-external",action="store_true");a.set_defaults(fn=cmd_run)
    a=sub.add_parser("judge");a.add_argument("project");a.add_argument("--run",required=True)
    a.add_argument("--success",choices=("yes","no"),required=True)
    a.add_argument("--reviewer",required=True);a.add_argument("--evidence-ref",required=True)
    a.add_argument("--feedback",default="");a.set_defaults(fn=cmd_judge)
    a=sub.add_parser("report");a.add_argument("project");a.add_argument("--output",required=True)
    a.set_defaults(fn=cmd_report)
    args=ap.parse_args(argv)
    if args.cmd=="judge": args.success=args.success=="yes"
    try:
        return args.fn(args)
    except (ValueError,OSError,KeyError,TypeError,AttributeError) as exc:
        print("ERROR:",exc,file=sys.stderr);return 1

if __name__=="__main__":
    sys.exit(main())
