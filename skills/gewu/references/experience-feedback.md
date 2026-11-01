# Gewu v0.4-EXP1 — 经验反馈优先级 1

## 目标

选择**10个过去实际执行过**的科研任务，比较：
A 无记忆执行与 B 使用独立外部验证的经验执行。

本仓库的 10 个候选任务类别见 [historical-task-candidates.md](historical-task-candidates.md)。目前仅做了来源 Skill 场景盘点，并未获取十个可完整回放的历史任务原始资料。因此不可声称已经完成真实试验或技能提升。

## 实施

`skills/gewu/scripts/gewu_experience.py` 提供：`freeze`（冻结10项任务/经验/协议），`run`（真实模型调用和 token 记录），`judge`（外部评价成功/失败以及修订意见），`report`（完整20组配对结果）。结构检查不替代外部人员判断。

实验目录必须预备三个 JSON 文件：

- `tasks.json`：`schema_version="0.4-exp1"`，10 条 `tasks`；每条有 task_id、origin_skill、original_request、task_type、prompt、context、tags、expected_artifact、external_success_criteria、historical_input_ref、historical_output_ref。
- `protocol.json`：相同 model、base_url、base_skill_file、max_revisions、input_usd_per_million、output_usd_per_million、cost_limit_usd；`success_rule="external_human_binary_verdict"`、`change_policy="freeze_before_both_arms"`。
- `experiences.json`：`schema_version="0.4-exp1"`，每条经验带 id、status、tags、trigger、action、reason、limits、verification_check、source_task_ids、verification（verdict、reviewer_id、evidence_ref、verified_at）。仅 `verified` 且外部核查通过的经验能够用于模型。经验来源不能是10个评估任务本身。

示例命令：

```bash
python skills/gewu/scripts/gewu_experience.py freeze pilot
python skills/gewu/scripts/gewu_experience.py run pilot --task T01 --arm no_memory --allow-external
python skills/gewu/scripts/gewu_experience.py run pilot --task T01 --arm verified_memory --allow-external
python skills/gewu/scripts/gewu_experience.py judge pilot --run pilot/runs/T01.no_memory.json --success no --reviewer researcher-001 --evidence-ref review/T01A1.md --feedback "缺少独立验证"
python skills/gewu/scripts/gewu_experience.py report pilot --output pilot/report.json
```

两组每次失败都需要外部评价及修订意见才允许再调用，直到通过或耗尽 `max_revisions`。记录实际输出 token 与输入 token，按照协议费率给出模型费用估算。

## 严格限制

1. 外部评审应独立、尽量盲法；程序只验证已录入的评审身份与证据链接存在字段，不认证评审者真实身份，也不证明评审公正。
2. 冻结后不得增删、更换任务或经验、改变费率和评分标准。
3. 缺少真实任务输入输出的候选类别不能算历史回放，且测试脚本中的合成成功率不代表现实结果。
4. 两组仅在加入独立验证的经验上不同；若经验文本泄露任务答案，该任务必须剔除并重新冻结完整实验。
5. 工具仅提供模型成本估算，人工审查成本、实际缓存定价及外部工具费需独立记录。
6. 外部成功率的提升是必要条件，但十题样本太少，不能据此宣称跨科研领域的稳定能力增长。

## 真实历史工件预检（2026-11-01补充）

本地可使用 `scripts/gewu_history_preflight.py` 对10项历史任务的原稿/修订稿进行 SHA-256 与 Office/PDF 结构校验，同时检查**逐字原始任务指令**及其来源定位是否存在。使用 `--strict` 时，只要有任何任务未恢复原始指令或校验失败，就会以非零状态结束，不允许声称该批任务已达到真实回放条件。

```bash
python skills/gewu/scripts/gewu_history_preflight.py /private/task_registry.private.json --strict --output /private/audit.json
```

**重要工程限制**：目前 `gewu_experience.py run` 的执行器只是文字聊天模型；它不会读取本地 DOCX、XLSX、PPTX 或 PDF 的原始字节并执行真实文件修改。把涉及文档或绘图的原任务压缩成一段文字提问，会改变研究任务定义，不能将聊天质量评分当作原任务成功率。应先配备按类型执行文件编辑、渲染和自动检查的工具，再在两组相同环境下比较；论文写作、电子表格和 PPT 的输出需分别验证。

2026-11-01 已在用户私人资料中取回并校验21份历史文件，组成10个原稿—修订稿候选链条。**逐字历史提示词未全部恢复、独立验证的经验库和真实外部评分尚缺，因此这仅是候选队列，不是完成评测的数据集。** 文件名、文献内容、源文件 ID 和私人哈希不应公开提交。
