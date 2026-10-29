---
name: gewu
description: 科研方向知识与研究方法蒸馏。用户希望从真实论文中梳理科学问题、实验设计、证据、研究分歧或生成可审查的方向 Skill 时使用。v0.3 支持本地 PDF 证据解析与跨论文候选规则分析。
metadata:
  version: "0.3.0"
---

# GEWU · 格物 — 科研蒸馏

## 目标

围绕**研究方向**而不是目标期刊，在真实文献中提取科学问题、方法选择、实验/评价设计、证据和反例，生成可审查的条件性科研规则。先形成研究贡献，再做期刊匹配。当前不实现人物或组织蒸馏。

## 工作顺序

1. 明确方向、数据与研究边界；制定检索、纳排、留出集与评价协议（`references/workflow.md`）。
2. 确保 PDF 来源合法且题录可核验；使用 `scripts/gewu_v03.py ingest` 解析本地 PDF，保留页码、段落 ID 与 SHA256。
3. 使用 `scripts/gewu_v03.py extract` 从原文定位研究问题、假设、数据、方法、基线、评价、结果和局限。无模型模式**只找原文候选片段**；模型模式也只能产出待审查解释。参见 `references/extraction.md`。
4. 在规则归纳前冻结综合集/留出集划分以及检索与评价协议；使用 `scripts/gewu_v03.py synthesize` 输出跨论文证据矩阵；在显式允许外部模型服务后可选择生成候选科研规则（`references/distillation.md`）。
5. 人工逐条核对原始 PDF 中的定位和引文、证据是否支持模型解释、是否有反例与遗漏变量；再使用旧脚本 `scripts/gewu.py check` 和 `compile` 生成方向 Skill。
6. 使用未参与蒸馏的论文和预注册指标完成独立测试；结果不理想时不可静默调整条件和评价方式（`references/validation.md`）。

## 使用边界

- **未检索**：不能说检索了文献；**只有摘要**：不能推断具体实验；**有 PDF 文本**：仍要核查复杂排版和公式。
- 模型提供的科学理解是候选解释，逐字引文匹配只是结构核查；**不是证据充分性验证**。
- 未经人工审查时禁止把候选规则发布为已经验证的技能；未经验证的内容必须明确标注。
- 留出论文绝不能进入方法规则归纳，也不得用测试表现反向挑选规则。
- 将 PDF 内容发送到外部模型前需征得授权，命令行使用 `--allow-external` 显式批准。
- 支持证据与反面证据都应保留；不能把两篇论文的结论差异抹平为共识。

## 命令入口

详情见仓库 `README.md`：

```bash
python skills/gewu/scripts/gewu.py init my-topic --topic "研究方向"
python skills/gewu/scripts/gewu_v03.py ingest my-topic --pdf paper.pdf --id p1 --title "论文题名"
python skills/gewu/scripts/gewu_v03.py extract my-topic --id p1
python skills/gewu/scripts/gewu.py freeze my-topic --part protocol
python skills/gewu/scripts/gewu.py freeze my-topic --part evaluation
python skills/gewu/scripts/gewu_v03.py synthesize my-topic
python skills/gewu/scripts/gewu.py check my-topic
```

运行前必须实填冻结协议，留出论文在蒸馏前确定。上述命令不包含外部模型调用，默认不能自动总结论文结论。已有 v0.2 项目继续兼容。
