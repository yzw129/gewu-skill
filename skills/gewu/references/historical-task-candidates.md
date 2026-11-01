# 10-task historical replay candidates

> These are **candidate task categories**, grounded in real open-source skill workflows. They are NOT yet 10 recovered, executed historical task transcripts. No success rates can be reported until original task prompts, input datasets, outputs, external reviews and usage logs are supplied.

| ID | 原始 Skill | 拟回放任务 | 当前缺口 |
|---|---|---|---|
| T01 | K-Dense-AI/scientific-agent-skills:literature-review | 科研综述检索式和纳排日志 | 需原始输入、原始输出、授权和外部评审 |
| T02 | VincenzoImp/academic-research-skills:digest-paper | 单篇文献证据和 DOI 核查 | 需原始输入、原始输出、授权和外部评审 |
| T03 | K-Dense-AI/scientific-agent-skills:hypothesis-generation | 提出竞争假设与可证伪预测 | 需原始输入、原始输出、授权和外部评审 |
| T04 | K-Dense-AI/scientific-agent-skills:experimental-design | 构建控制混杂因素的实验设计 | 需原始输入、原始输出、授权和外部评审 |
| T05 | K-Dense-AI/scientific-agent-skills:scientific-critical-thinking | 审查错误因果推断和遗漏变量 | 需原始输入、原始输出、授权和外部评审 |
| T06 | K-Dense-AI/scientific-agent-skills:peer-review | 核查稿件核心科学主张与证据 | 需原始输入、原始输出、授权和外部评审 |
| T07 | VincenzoImp/academic-research-skills:develop-contribution | 比较最接近研究并设计创新验证 | 需原始输入、原始输出、授权和外部评审 |
| T08 | VincenzoImp/academic-research-skills:adversarial-review | 在投稿前指出影响结论的实质性错误 | 需原始输入、原始输出、授权和外部评审 |
| T09 | jmiao24/Paper2Agent:paper2mcp | 基于论文代码重放运行并对照输出 | 需原始输入、原始输出、授权和外部评审 |
| T10 | K-Dense-AI/scientific-agent-skills:scientific-visualization | 复核科研图件的数据、单位和误差表达 | 需原始输入、原始输出、授权和外部评审 |

## 评价约束

- 10 个任务与能力标签、输入及外部成功标准在开始两组调用前固定。
- 经验来源任务必须与这10个评估任务完全隔离，且人工核对其内容和适用范围。
- 两组保持同一基础 Skill、同一模型配置及原始任务上下文；记忆组只增加事先冻结的已验证经验。
- 修改次数 = 实际尝试次数 - 1；如果因失败达到预算，则仍为失败，不能丢弃。
- 成本 = 所有调用的输入与输出 token × 冻结的每百万 token 费率；此为估算，不是实际账单。
- 事先固定主要指标成功率和次指标修改次数及成本；只在成功率提升且两个次指标不恶化时记录探索性正面结果，不能自动升级长期经验。
- 当前尚无10条已整理的历史真实执行记录，也无外部评分和 API 计费凭证。因此没有真实 A/B 结果。

