# Changelog

## v0.3.0 — 2026-10-29

- 新增 `gewu_v03.py ingest`：读取本地文字型 PDF，按页和结构标题形成可定位片段，保存内容和 PDF SHA-256。
- 新增 `gewu_v03.py extract`：离线关键词候选段落定位；可选调用兼容 Chat Completions 的外部模型，强制 passage ID 和逐字引文校验。
- 新增 `gewu_v03.py synthesize`：基于冻结的研究协议和留出计划构建跨论文证据矩阵；外部模型模式产生未审核规则候选，至少引用两篇不同论文。
- 保留 v0.2 的审查与编译机制，新增证据来源 `other/references` 的结构兼容。
- 新增 PDF 端到端合成测试、`.gitignore`、依赖清单与 GitHub Actions 软件测试。
- 不声称已经完成真实论文科学效果验证或自动全文检索。

## v0.2.0

- 初始化研究项目、证据审查、冻结、候选规则编译与报告功能。