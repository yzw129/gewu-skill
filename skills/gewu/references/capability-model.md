# Gewu v0.5 通用能力蒸馏契约

## 核心概念

能力不是知识条目列表。一个能力卡必须回答：
- **触发条件**：何时使用规则；
- **可执行行动**：有什么输入、产出和步骤；
- **证据依据**：来源是什么，有无许可，是否实际核查；
- **失效条件**：哪些前提变化会使方法失效；
- **验证标准**：如何检查真实产物而非只看模型自述。

四个模块分别调用 `domains/{research,writing,visualization,presentation}/SKILL.md`，共享校验器和版本记录，专门评价指标由模块自己规定。

## 能力证据来源

可接受科研论文、开源 Skill、官方规范、代码、授权作品、真实失败记录。每个来源必须记录 id、kind、title、location、locator、reviewed、usage_rights。来源被标为 reviewed 只代表**使用者声明已核对**，不代表程序已经核查真实性或许可。

每条规则须包含 id、status、trigger、action、why、exceptions、verification、source_ids。候选规则仅生成 preview；reviewed 还需要评价计划冻结才能生成正式版，正式版仍标记“尚未完成独立能力验证”。

## 四种能力的检验策略

- 研究：科学证据、问题可证伪、实验有效、反例处理。
- 写作：科学事实与图表一致、论证结构、引文准确、清晰性。
- 绘图：数据忠实、科学关系正确、可读性与复现性。
- 汇报：内容事实、叙事、视觉层级、原生可编辑能力。

具体评分需要基于真实任务和人工判定。模型自评、高分生成质量、程序测试通过都不是技能迁移增益的充分证据。

## 模块独立与协作

科研成果准备通常为：证据核查 → 科研推理 → 数据作图 → 结果写作 → 汇报。分模块蒸馏后再在组合任务上测试；否则无法判断性能差异来自哪一种能力。

## 版本和独立评价

`gewu_capabilities.py` 是通用能力卡与 Skill 编译器；`gewu_eval_v041.py` 是现有科研三组对照。v0.5 尚未把各领域产物自动评分、文字版前后差异或渲染视觉评估接入通用评分器。

评价计划必须先固定开发题、测试题及领域量表，并使用冻结指纹防止静默修改。参与能力蒸馏的素材不能再作为独立测试来源。测试集只用于最终确认，不应供优化同一轮规则。

## 外部项目的具体借鉴

- [Scientific Writing](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-writing/SKILL.md)：主张—证据绑定、方法与结果一致性、写作版本核对。
- [Scientific Visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-visualization/SKILL.md)：坐标与数据忠实性、可访问性、导出与实图检查。
- [Scientific Schematics](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-schematics/SKILL.md)：概念机制图和生成后检查；注意图像式输出的不可编辑限制。
- [Scientific Slides](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-slides/SKILL.md)：叙事与设计统一、量化图应保留事实依据与源文件。
- [Matplotlib](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/matplotlib/SKILL.md)：可复现脚本、可缩放矢量格式与布局控制。

这些是经过源代码阅读提炼的设计思路，不是直接复制原项目代码或宣布获得项目原作者的技术能力；使用外部代码和作品须另行遵守各自许可。
