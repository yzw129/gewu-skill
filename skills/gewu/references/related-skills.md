# 从其他科研 Skill 中迁移方法的准则（v0.4.1）

本文件记录分析过的公开项目与可迁移机制，**不是复制原项目的 Skill**。所有机制必须独立验证。

| 来源 | 直接核验的入口 | 提炼的机制 | Gewu 采用方式 |
|---|---|---|---|
| K-Dense Scientific Agent Skills / literature-review | https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/literature-review/SKILL.md | 检索日志、论文/记录区分、筛选边界 | 文献库标注数据库、检索式、去重和纳排理由；不把搜索结果等同于已读全文 |
| K-Dense / hypothesis-generation | https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/hypothesis-generation/SKILL.md | 竞争假设、可证伪预测、观测与推断目标区分 | 科研行动规则附反例、关键观测和失败判据 |
| K-Dense / experimental-design | https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/experimental-design/SKILL.md | 实验单元、伪重复、混杂控制 | 方法规则须记录实验单位和对照设计 |
| K-Dense / scientific-critical-thinking | https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-critical-thinking/SKILL.md | 主张—证据质量—适用范围审查 | 证据事实/研究推断/新假设分开 |
| VincenzoImp / digest-paper | https://github.com/VincenzoImp/academic-research-skills/blob/main/skills/digest-paper/SKILL.md | 单篇论文作为可追踪的原子档案 | 每篇论文保存文献版本、全文状态、定位证据与核查结果 |
| VincenzoImp / develop-contribution | https://github.com/VincenzoImp/academic-research-skills/blob/main/skills/develop-contribution/SKILL.md | 创新点必须对应已有方法差异和可反证实验 | 新科学问题应记录最接近既有研究及反驳条件 |
| VincenzoImp / adversarial-review | https://github.com/VincenzoImp/academic-research-skills/blob/main/skills/adversarial-review/SKILL.md | 原始主张先于评语，严重性和修复证据分离 | 蒸馏规则必须完成对抗式证据复查 |
| kinqsradio / research-design | https://github.com/kinqsradio/academic-research-skills/blob/main/skills/research-design/SKILL.md | 目标量、观测单位、设计决策和研究阶段的区分 | 区分“建议开展”“已实施”“已验证” |
| Paper2Agent / paper2mcp | https://github.com/jmiao24/Paper2Agent/blob/main/skills/paper2agent/paper2mcp/SKILL.md | 可运行代码绑定真实方法；原始执行后独立验证 | 若论文附代码，可选复现实验；不因论文有代码就认为结果已复现 |

## 需要避免的误用

- 不复制其他项目的大段提示词、完整代码或未经核实的项目声明；引用只定位方法来源。
- 不把临床研究的特定偏差评价框架未经转换应用于水文、遥感和工程模拟。
- 不把整套写作、绘图、选刊 Skill 全部并入 Gewu 的蒸馏核心。
- 不把“检索了多少篇文章”当成科研推理能力指标，也不能把自动评分当独立科学验证。
- 不让测试集论文出现在训练/蒸馏资料或开发集反馈里。

## 最优先的改变：三组对照

A（baseline）：没有新增文献资料与科研 Skill。

B（retrieval）：获得固定的相同文献证据包，不加载 Skill。

C（skill）：与 B 使用**字节相同的证据包**，再加载科研行动协议。

主要效应是 C−B。A−B 反映文献额外信息的影响；C−A 为综合影响。若没有 B 组，无法判断性能提高主要来自更多事实还是来自科研推理方法。

执行脚本：`scripts/gewu_eval_v041.py`。它进行证据包 SHA256 一致性检查，输出配对盲审数据结构；科学效果必须依赖真实模型运行、冻结评价和人工评审。

### 进一步研究的方向（尚未实现）

1. 系统化论文身份校验与复现资产检查（代码、数据、许可证、运行环境）。
2. 科研方法卡：IF/THEN/BECAUSE/EXCEPT/CHECK 加实验单位、混杂因素、转移条件和置信度。
3. 双人独立评审一致性、多个随机种子与效应不确定性。
4. 知识增益与流程增益的跨方向迁移验证。
