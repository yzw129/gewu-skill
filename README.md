# GEWU Skills · 格物（Research Edition v0.2）

> **当前优先级：只实现科研方向蒸馏。** 人物、组织、项目、风格等非科研模式不在 v0.2 内。未来可以增加模式，但不能牺牲当前的科研证据可追溯性。

**定位：** 利用真实研究文献和研究者提供的资料，归纳科学问题、研究方法、实验设计、论证规则，并将人工核查过的规则整理成方向专属 Agent Skill。研究方向优先，期刊匹配放在研究贡献初步明确之后。

## v0.2 实际已实现

- 兼容 Agent Skills 的 `skills/gewu/SKILL.md` 主指令和科研方法协议。
- `gewu.py init`：创建方向项目与数据模板。
- `gewu.py check`：离线检查必需字段、重复引用、来源层级、错误引用、留出论文污染、规则证据审查状态。
- `gewu.py freeze`：记录检索协议与独立评估计划指纹，提示冻结后被改动的配置。
- `gewu.py compile`：把已登记为“人工核对”的规则编译成方向 Skill，未经审查规则仅可用 `--preview` 输出草稿。
- `gewu.py report`：报告论文、证据层级、规则与留出集的当前状态。
- 8 个合成案例自动测试；测试用文章完全虚构且仅存在于测试代码中，不作为科研证据。

## v0.2 尚未实现

- 自动联网检索、下载全文、PDF 解析、自动提取与跨论文语言模型归纳。
- DOI 和文章内容的在线真实性核查。
- 自动找出科学创新点或独立确认研究结论。
- 在真实留出论文上比较蒸馏 Skill 与通用模型的效果。

**请不要将结构测试通过解释为已经实现自动科研蒸馏。** 目前科研证据的分析需由兼容 Agent 按 `SKILL.md` 和协议完成，并保留实际来源，Python 脚本管理记录与编译。

## 安装

将 `skills/gewu` 复制到支持 Agent Skills 的客户端 Skills 目录，或将 `SKILL.md` 作为主控指令交给支持读写文件与科研文献工具的智能体。不同宿主的安装位置和权限不同；本项目没有自动执行未知宿主中的工具。

Python 依赖：Python 3.9+ 标准库，不需要额外依赖。

## 本地命令

在仓库根目录运行：

```bash
python skills/gewu/scripts/gewu.py init my-research --topic "物理引导降雨径流模拟" --scope "产流汇流与极端洪水泛化"
python skills/gewu/scripts/gewu.py check my-research
python skills/gewu/scripts/gewu.py report my-research
```

手工或使用智能体按科研协议补充 `project.json` 的检索式与纳排标准后，冻结检索协议：

```bash
python skills/gewu/scripts/gewu.py freeze my-research --part protocol
```

检索真实论文，形成 `papers.json` 和可定位证据；在蒸馏之前将部分论文标为 `pool=holdout`，并将其 ID 加入 `project.json` 的 `evaluation.holdout_ids`，随后冻结评估计划：

```bash
python skills/gewu/scripts/gewu.py freeze my-research --part evaluation
```

继续形成 `rules.json`。若有人逐条审查文献证据，将相应项的 `review_status` 标为 `checked`，规则改为 `reviewed`。在此基础上：

```bash
python skills/gewu/scripts/gewu.py check my-research
python skills/gewu/scripts/gewu.py compile my-research
```

输出目录为 `my-research/generated_skill/`，包含方向 `SKILL.md` 与 `references/rules.md`。如果尚未核查规则，可运行 `compile ... --preview`，但输出中会显著声明未经核验，不能作为可信技能发布。覆盖已有结果需 `--force`。

## 核心数据

```text
my-research/
├── project.json             # 研究边界、检索协议、留出计划和冻结状态
├── papers.json              # 真实论文身份、阅读层级、抽取记录、分组
├── rules.json               # 有条件、证据支持的科研方法规则
├── screening_log.md         # 数据库、日期、检索式、去重/纳排日志
├── evaluation.md            # 独立评估证据与对照结果（人工填写）
└── generated_skill/         # 编译后才创建
```

具体字段可从 `skills/gewu/templates/` 查看。**对于不满足阅读层级的细节，不能由摘要推断正文内容。**

## 证据与验证分层

1. **结构正确**：脚本检查 JSON、交叉引用、留出隔离、配置指纹。
2. **文献真实且理解正确**：独立回看原始 PDF、论文与 DOI，审查模型误读和推断越界。
3. **蒸馏规则有用**：用固定留出集，与无蒸馏基础模型和直接检索做对比。

只有三层分别满足要求，才能报告相应结论。评估前固定指标、测试论文和模型版本，禁止看到结果后静默改写规则。

## 第一轮研究样例

`examples/hydrology-pilot/` 是空的水文学研究方向项目，只定义了测试范围，不包含任何假论文或虚构结论。

## 未来接口（本版不开发）

后续可在保持 `project → source → rule → skill → evaluation` 核心数据关系的基础上增加其他蒸馏模式，但必须为不同领域单独定义真实性和效果标准。科研版不是人物模仿器。