# Gewu Skills · 格物（Research Edition v0.3）

> **目标：科研方向蒸馏。** 方向文献 → 带页码的 PDF 证据 → 科研问题/方法候选 → 跨论文证据比较 → 有条件的候选规则 → 人工核对 → 方向专属 Skill。期刊选择在研究贡献形成之后。

**v0.3 已实现：** 使用 PyMuPDF 读取**用户合法获取的本地文字型 PDF**，保存页码、段落编号、文本哈希和 PDF 文件哈希；从原文中筛选对应科研要素的候选段落；在冻结检索和留出协议后生成跨论文证据矩阵；可选择调用兼容 Chat Completions 接口的外部大模型提炼保守的候选结论；校验它引用的 passage ID 与逐字引文；保留 v0.2 的审查和 Skill 编译功能。

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