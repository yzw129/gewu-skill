# Gewu Skills · 格物（通用能力蒸馏 v0.5）

> **定位升级**：通用能力蒸馏与验证引擎。第一批模块为科研推理、学术写作、科学绘图、学术汇报。核心框架负责来源、规则、审查、冻结和编译，各领域模块拥有独立的执行方法与评价标准。

**注意**：v0.5 新增的是跨领域能力卡与编译器，并没有自动学会写论文、画图、制作 PPT，也没有训练基础模型参数。源码/流程的结构测试通过，不等于真实作品或能力迁移已被验证。

## 通用能力卡操作

```bash
# 为论文写作建立能力蒸馏项目；其他可用 research / visualization / presentation
python skills/gewu/scripts/gewu_capabilities.py init my-writing --id paper-writing --domain writing

# 填写 my-writing/capability.json 中真实来源、证据、候选规则和检查方法
# 在 my-writing/evaluation.json 中替换开发集与测试集的占位任务
python skills/gewu/scripts/gewu_capabilities.py check my-writing
python skills/gewu/scripts/gewu_capabilities.py freeze my-writing

# candidate 规则只能生成明确标记的未核查预览
python skills/gewu/scripts/gewu_capabilities.py compile my-writing --preview --output my-writing/preview

# 每条来源完成审查，规则标记 reviewed 后才允许正式编译
python skills/gewu/scripts/gewu_capabilities.py compile my-writing --output my-writing/skill-v1
```

**数据契约**：`capability.json` 保存领域、来源（含使用权限）、能力规则及状态；`evaluation.json` 保存领域专属评价维度、开发集与独立测试集。规则字段为 IF/THEN/BECAUSE/EXCEPT/CHECK。`evaluation.lock.json` 锁定评价计划指纹。

## 领域能力模块

- [科研推理](skills/gewu/domains/research/SKILL.md)
- [学术写作](skills/gewu/domains/writing/SKILL.md)
- [科学绘图](skills/gewu/domains/visualization/SKILL.md)
- [学术汇报](skills/gewu/domains/presentation/SKILL.md)

统一契约见 [能力模块与评估协议](skills/gewu/references/capability-model.md)。

## 和旧版本的关系

- v0.3：科研文献 PDF 的证据提取；
- v0.4：科研推理协议、开发/测试分离；
- v0.4.1：科研三组对照，区分文献知识和方法指令的效果；
- **v0.5**：新增跨领域模块，允许写作、绘图、学术汇报作为不同种类的待蒸馏能力。

**兼容性**：旧版 `gewu.py`、`gewu_v03.py`、`gewu_v04.py`、`gewu_eval_v041.py` 不移除，科研研究项目数据结构保持原样；新领域使用独立能力项目格式，尚未实现旧科研项目自动迁移。

---

## v0.4.1 及之前的科研流程（历史操作说明）


> **目标：科研方向蒸馏。** 方向文献 → 带页码的 PDF 证据 → 科研问题/方法候选 → 跨论文证据比较 → 有条件的候选规则 → 人工核对 → 方向专属 Skill。期刊选择在研究贡献形成之后。

**v0.3 已实现（仍保留）：** 使用 PyMuPDF 读取**用户合法获取的本地文字型 PDF**，保存页码、段落编号、文本哈希和 PDF 文件哈希；从原文中筛选对应科研要素的候选段落；在冻结检索和留出协议后生成跨论文证据矩阵；可选择调用兼容 Chat Completions 接口的外部大模型提炼保守的候选结论；校验它引用的 passage ID 与逐字引文；保留 v0.2 的审查和 Skill 编译功能。

**v0.3 未实现：** 自动网络检索/批量下载论文、法律意义的全文使用授权检查、扫描 PDF OCR、复杂公式与表格的可靠结构解析、论文元数据在线核验、自动证明科学结论、自动接受规则为可靠事实、真实留出集的系统性评估。**当前所有提取与归纳规则均为未审查候选。**

## 安装与环境

- Python 3.9+。核心旧命令只依赖标准库；PDF 解析额外依赖 `PyMuPDF`。
- 安装：`python -m pip install -r requirements.txt`。
- 开发测试：`python -m pip install -r requirements-dev.txt`。
- 主 Skill：`skills/gewu/SKILL.md`；旧版脚本：`skills/gewu/scripts/gewu.py`；v0.3 脚本：`skills/gewu/scripts/gewu_v03.py`。

## 10 分钟体验：不用调用外部模型

在仓库根目录执行：

```bash
python skills/gewu/scripts/gewu.py init my-topic --topic "物理引导降雨径流模拟" --scope "物理产汇流过程与泛化能力"
python skills/gewu/scripts/gewu_v03.py ingest my-topic --pdf "/path/to/paper1.pdf" --id paper01 --title "请填真实题名" --doi "10.xxxx/xxxx"
python skills/gewu/scripts/gewu_v03.py ingest my-topic --pdf "/path/to/paper2.pdf" --id paper02 --title "请填真实题名"
python skills/gewu/scripts/gewu_v03.py ingest my-topic --pdf "/path/to/paper3.pdf" --id paper03 --title "请填真实题名" --pool holdout
python skills/gewu/scripts/gewu_v03.py extract my-topic --id paper01
python skills/gewu/scripts/gewu_v03.py extract my-topic --id paper02
```

注意：`--title` 由使用者填写并核实；自动识别的 PDF 内 DOI **尚未在线校验**。论文初始登记为 included 只是“输入语料”，正式纳排仍需人工检查。建议先按文献筛选规则确定研究方向、样本和留出集，避免随意选样导致方向偏差。

编辑 `my-topic/project.json` 中 `protocol.sources`、`protocol.queries`、`protocol.inclusion`、`protocol.exclusion`、`evaluation.holdout_ids`；论文 `paper03` 已设为 `pool=holdout`。然后冻结（留出论文必须在归纳之前登记）：

```bash
python skills/gewu/scripts/gewu.py freeze my-topic --part protocol
python skills/gewu/scripts/gewu.py freeze my-topic --part evaluation
python skills/gewu/scripts/gewu_v03.py synthesize my-topic
python skills/gewu/scripts/gewu.py check my-topic
```

本地模式只生成 `my-topic/analysis/evidence_matrix.json`，**不会凭关键词生成科学结论或写入 `rules.json`**。不同论文的对应片段可从矩阵中逐项阅读。

## 可选：由外部模型生成候选科研解释和跨论文规则

先阅读模型提供商的文献上传/数据处理政策。调用外部服务会发送原文片段，必须获得所需授权；只在用户自愿允许时使用。

```bash
# Linux / macOS；Windows PowerShell 用 $env:OPENAI_API_KEY="..."
export OPENAI_API_KEY="你的密钥"
export GEWU_LLM_MODEL="你的模型名称"
export GEWU_LLM_BASE_URL="https://api.openai.com/v1"
python skills/gewu/scripts/gewu_v03.py extract my-topic --id paper01 --provider llm --allow-external --replace
python skills/gewu/scripts/gewu_v03.py extract my-topic --id paper02 --provider llm --allow-external --replace
python skills/gewu/scripts/gewu_v03.py synthesize my-topic --provider llm --allow-external
```

具体接口为 `POST {BASE_URL}/chat/completions`；服务商需兼容这一格式，否则需适配。模型名称由用户按当前服务配置决定；本仓库不提供 API 密钥、模型账号或下载权限。默认只允许 HTTPS。`--allow-external` 是数据出站的显式授权开关。

**约束：** 模型只能引用传入的证据 ID；逐字引文必须出现在对应 PDF 片段中；跨论文规则至少引用两篇综合集论文；留出论文不能参与提炼；规则写为 `status=candidate`、`review_status=unchecked`。但引文精确匹配只能证实文本位置，**不能保证模型理解正确**。必须回看论文、开展反例检索并人工审查。

## 人工审查与方向 Skill

人工核验候选规则后，在 `rules.json` 中将证据 `review_status` 标记为 `checked`、开展反例检索并记录，再将规则标记 `reviewed`：

```bash
python skills/gewu/scripts/gewu.py check my-topic
python skills/gewu/scripts/gewu.py compile my-topic
```

未经审查只允许 `compile ... --preview`，且生成内容明确标注未验证。`compile` 不会自动检查 DOI 真实性或科学推断有效性。

## 数据结构

```text
my-topic/
├── project.json                 # 范围、检索协议、留出集与冻结状态
├── papers.json                  # 论文元数据及来源层级（需人工核查）
├── corpus/<paper_id>.json       # PDF 原文片段、页码、段落ID及 SHA256
├── extracts/<paper_id>.json     # 逐条科研要素候选和可定位原文
├── analysis/evidence_matrix.json
├── analysis/synthesis_trace.json # 仅模型模式生成
├── rules.json                  # 跨论文规则（候选，待审查）
├── screening_log.md            # 真实检索与筛选日志（自行维护）
├── evaluation.md               # 留出评估记录（自行维护）
└── generated_skill/            # 人工审核后生成
```

默认 `.gitignore` 忽略研究者本地的 PDF/语料/模型提取记录和 API 配置；请勿将未授权全文或含密钥文件提交公共仓库。`corpus` 与 `extracts` JSON 也含论文原文，分享前同样需审查授权。

## 运行测试

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

测试数据为**程序生成的合成 PDF**，用于验证解析、证据 ID、引文核验、留出保护、冻结和编译流程。测试通过只说明软件逻辑按预期执行，**尚未在真实论文集合上验证科研蒸馏效果**。CI 同样只做程序测试。

## 来源与限制

- 文献 DOI、题名、年份、版本、作者信息必须核验；PDF 页面文字型提取可能打乱双栏、表格和公式。对扫描型 PDF，工具拒绝将其记为完整可读全文。
- 自带的关键字定位器只是召回候选段落，不是可靠的语义理解；每篇文章的部分段落会因样本限制未提供给模型，输出中记录覆盖提醒。
- 来源 hash 与引用匹配检测的是本地数据一致性，无法自动证明 PDF 未被篡改或来源可靠。
- 不允许以高频方法或高引论文代替因果与实验论证。对不同研究的结果分歧，应保留适用范围和反例。
- 发布方向 Skill 前冻结评估计划、独立留出集、规则和评分办法，避免结果驱动修改。

## 设计理念

科研蒸馏不是复制高水平论文的句式，而是从可追溯证据中提炼“在什么条件下、为解决什么问题、怎样设计与验证”的方法规则。当前仅实现科研模式，保留其他领域未来扩展的可能。
---

## v0.4：从科研信息蒸馏到科研行动与能力评估

**版本定位**：v0.3 仍负责本地 PDF 文献解析与跨论文候选规则；v0.4 额外把经人工核验的科研规则编译为 IF→THEN→BECAUSE→EXCEPT 行动协议，并提供同模型配对盲审、开发集定向修订和隔离测试集。不训练模型权重，不自动宣称能力增长。

### 1. 生成具备行动流程的方向 Skill

在完成 v0.3 的研究证据归纳、人工核查并将对应 rules.json 条目标记为 reviewed 之后：

\`\`\`bash
python skills/gewu/scripts/gewu_v04.py build my-topic --output my-topic/agent/versions/v1
\`\`\`

生成的 \`SKILL.md\` 不只是研究结论列表，而包含科研问题界定、可辨识性、可证伪假设、实验对照、证据核对与结论边界六个关卡。它附带规则来源索引和规则文件指纹。没有审核过的规则不能正式构建。

### 2. 创建并冻结新任务基准

\`\`\`bash
python skills/gewu/scripts/gewu_v04.py init-bench my-topic
\`\`\`

修改 \`my-topic/evaluation/benchmark.json\` 中 dev/test 的占位问题与独立上下文；任务样例需覆盖文献中未直接给出的新科研问题，并在适用时通过 \`source_paper_ids\` 标识论文来源。先完成 v0.2 的 \`freeze --part evaluation\`，然后：

\`\`\`bash
python skills/gewu/scripts/gewu_v04.py freeze-bench my-topic
\`\`\`

冻结后任何问题、维度或分组变更都会使运行拒绝继续，必须创建新版本。不要把测试集问题和其参考答案交给蒸馏模型。

### 3. 同条件比较有无 Skill（可选 API，需授权）

\`\`\`bash
export OPENAI_API_KEY="配置自己的密钥"
export GEWU_LLM_MODEL="配置的模型"
python skills/gewu/scripts/gewu_v04.py run my-topic --split dev --arm baseline \
  --output my-topic/evaluation/runs/dev-baseline.json --allow-external
python skills/gewu/scripts/gewu_v04.py run my-topic --split dev --arm skill \
  --skill my-topic/agent/versions/v1/SKILL.md \
  --output my-topic/evaluation/runs/dev-skill.json --allow-external
\`\`\`

运行命令通过兼容 Chat Completions 的模型接口访问外部服务。需保证两组使用同一模型、提供同样的任务上下文；模型输出和提示词指纹会记录到本地。**尚未实际对真实外部科研模型运行这一流程；测试覆盖的是模拟接口和程序不变量。**

### 4. 生成盲审与评分

\`\`\`bash
python skills/gewu/scripts/gewu_v04.py blind my-topic \
  --baseline my-topic/evaluation/runs/dev-baseline.json \
  --skill my-topic/evaluation/runs/dev-skill.json \
  --packet my-topic/evaluation/grades/dev-blind.json \
  --mapping my-topic/evaluation/private/dev-map.json
\`\`\`

将盲审包交给评分者，**不要提供秘密映射文件**。评分文件示例（每个 \`case_id\` 必须覆盖）：

\`\`\`json
{"grades":[{"case_id":"盲审包内的ID","reviewer":"reviewer-A",
  "scores":{"evidence":3,"question":4,"experiment":3,"limitations":2}}]}
\`\`\`

评分完成后：

\`\`\`bash
python skills/gewu/scripts/gewu_v04.py score \
  --packet my-topic/evaluation/grades/dev-blind.json \
  --mapping my-topic/evaluation/private/dev-map.json \
  --grades my-topic/evaluation/grades/dev-reviewed.json \
  --output my-topic/evaluation/dev-report.json
\`\`\`

### 5. 根据 dev 失败生成候选版本，而非偷看 test

写一个修订计划：

\`\`\`json
{"changes":[{"failure_task_ids":["dev-task-001"],
"trigger":"资料稀缺且缺少独立外部检验时",
"new_action":"先检查目标可辨识性，再增加对照与可证伪失败判据",
"rationale":"开发集盲审指出实验设计缺少失败判据；待进一步验证"}]}
\`\`\`

\`\`\`bash
python skills/gewu/scripts/gewu_v04.py evolve my-topic \
  --base-skill my-topic/agent/versions/v1/SKILL.md \
  --dev-report my-topic/evaluation/dev-report.json \
  --revision my-topic/evaluation/revision.json \
  --output my-topic/agent/versions/v2-candidate
\`\`\`

\`evolve\` 拒绝 test 报告，不会覆盖 v1；输出带 \`NOT_APPROVED\` 标记。候选版本复测开发集，锁定后**一次性**评价独立 test；不得根据 test 结果在同一测试集上再次调优。此流程不自动判断科研规律的真伪，也不做参数微调。

**当前可验证的改进**是：研究 Skill 的行动流程可执行、任务对照过程可记录、改进与测试分离；至于是否真正提升新研究问题的科学推理质量，需要真实论文、独立任务和人工评价后才能判断。


## v0.4.1 外部科研 Skill 方法借鉴与三组比较

相关项目及源代码检查记录见 `skills/gewu/references/related-skills.md`，重点吸收原子文献档案、假设与竞争解释、实验设计和主张审查，而非直接复制 Skill。

与原来的双组对照相比，新脚本 `skills/gewu/scripts/gewu_eval_v041.py` 支持三组：`baseline`（无补充资料）、`retrieval`（固定证据资料）、`skill`（相同资料+研究协议）。重点比较 skill 与 retrieval，避免把单纯获得新文献的收益误归因于科研方法蒸馏。

典型调用（先使用 v0.4 的 `freeze-bench` 冻结评估题目和评分）：

```bash
python skills/gewu/scripts/gewu_eval_v041.py run my-topic --split dev --arm baseline --output base.json --allow-external
python skills/gewu/scripts/gewu_eval_v041.py run my-topic --split dev --arm retrieval --evidence-pack evidence.md --output retrieval.json --allow-external
python skills/gewu/scripts/gewu_eval_v041.py run my-topic --split dev --arm skill --evidence-pack evidence.md --skill my-topic/agent/versions/v1/SKILL.md --output skill.json --allow-external
python skills/gewu/scripts/gewu_eval_v041.py blind my-topic --baseline base.json --retrieval retrieval.json --skill skill.json --packet blinded.json --mapping secret.json
python skills/gewu/scripts/gewu_eval_v041.py score --packet blinded.json --mapping secret.json --grades human_grades.json --output paired_report.json
```

调用外部模型需要明确授权，并配置与 v0.4 相同的 API 环境变量。没有模型调用和实际人工评分，不能称评估已经验证。评分采用现有 v0.4 四维标准；`evolve` 仍只接收旧双组格式，**v0.4.1 三组评分报告不会自动接入进化模块**，需进一步开发适配，禁止误称闭环已全部打通。
