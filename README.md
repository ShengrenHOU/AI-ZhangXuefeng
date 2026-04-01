# AI-ZhangXuefeng

[中文](#中文说明) | [English](#english)

## 中文说明

### 项目是什么

`AI-ZhangXuefeng` 是一个面向普通家庭的高考志愿助手。  
它不是“输入分数直接出学校名单”的黑箱工具，而是一个**对话驱动、模型主导推荐、知识优先检索、来源可追溯**的决策产品。

系统目标是帮助用户在家庭预算、兴趣方向、城市偏好、调剂态度、风险偏好等现实约束下，逐步形成一份更稳妥、可解释、可讨论的志愿草案。

### 为什么要做

高考志愿场景的真实痛点，不是“缺一个会聊天的大模型”，而是：

- 信息来源碎片化
- 家庭约束难以结构化表达
- 推荐结果常常不可解释
- 很多工具把模型放在规则前面，导致结果不可控

这个项目的设计选择是反过来的：

- **对话优先**：先把学生档案补完整
- **模型主导推荐**：最终推荐由大模型结合已发布知识和专业判断生成
- **最小硬护栏**：代码负责成熟度门槛、明显冲突、审计记录，而不是替模型拍板
- **知识治理优先**：线上只读已发布知识，不直接拿开放网页参与正式推荐
- **来源可追溯**：每条推荐都必须能回到来源记录

### 当前架构

项目采用双运行时思路：

- **在线主链路**
  - 对话状态机
  - 学生 dossier 补全
  - 已发布知识库检索
  - 模型负责抽取、追问、推荐、解释、组织结构化输出
  - Recommendation Core 仅作为 fallback / guardrail 保留

- **离线知识运营**
  - 原始信息采集
  - 章程抽取与结构化
  - 版本差异检测
  - 待审核任务生成
  - 审核通过后发布到正式知识库

Phase 1 已实现的是**在线 MVP 骨架**。离线知识运营链路留作后续增强。

### 当前能力

- 单省份试点：`henan`
- 单年份试点：`2026`
- 对话式学生画像补全
- `reach / match / safe` 结构化分桶
- 推荐 trace 与 source ID 绑定
- 学校/专业对比接口骨架
- 家庭摘要导出接口骨架
- 已发布知识与草稿知识分层

### 技术选择

- 前端：Next.js
- 后端：FastAPI
- 在线编排：typed state machine
- 模型接入：Ark Coding Plan OpenAI-compatible endpoint
- 当前默认模型：`minimax-m2.5`
- 数据层：PostgreSQL 为目标形态，开发可回退 SQLite
- 协议：MIT License

### 部署后应如何使用

这是一个“部署后打开即用”的 Web 产品，而不是只面向本地命令行用户的脚手架。

部署完成后，访问者应能直接获得以下体验：

- 打开首页，进入对话式志愿助手
- 系统逐轮追问关键信息，形成学生 dossier
- 档案足够后，生成结构化 shortlist
- 查看推荐理由、风险提示、来源详情
- 进入 compare 页面做方案对比
- 导出家庭讨论版总结

### 运行时配置

在线模型接入已切换到 Ark Coding Plan，关键配置为：

- Base URL: `https://ark.cn-beijing.volces.com/api/coding/v3`
- Model: `minimax-m2.5`
- Auth: Ark API Key

注意：

- 必须使用 Coding Plan 专用地址
- 不应使用 `https://ark.cn-beijing.volces.com/api/v3`
  否则不会走 Coding Plan 套餐额度，而会产生额外费用

### 仓库结构

- `apps/web`: Web 产品壳层
- `services/api`: 在线状态机、API、推荐编排
- `packages/types`: 共享契约与 schema
- `packages/recommendation-core`: 决定性推荐核心
- `packages/knowledge`: 已发布知识、草稿知识、来源索引
- `tools/ingestion`: 离线知识导入与发布脚手架
- `docs`: 架构、契约、治理、协作规范

### 开源协议选择

本仓库采用 **MIT License**。

原因：

- 适合产品早期快速迭代和公开协作
- 允许个人和商业团队较低摩擦地复用
- 不强制衍生项目开源，利于后续生态扩展
- 与当前代码栈和项目目标兼容，简单清晰

如果后续你希望把“品牌名、数据资产、已发布知识库内容”与代码许可拆开治理，可以在 MIT 代码协议之外，再补单独的数据和品牌使用规则。

---

## English

### What This Project Is

`AI-ZhangXuefeng` is a dialogue-first gaokao planning assistant for ordinary families.  
It is not a black-box score-to-school generator. It is a **workflow-driven, model-led, knowledge-first, source-traceable** decision product.

The goal is to help users build a safer and more explainable application shortlist under real-world constraints such as budget, major interests, city preference, adjustment tolerance, and risk appetite.

### Why It Exists

The real problem in gaokao planning is not the absence of a chat model. The real problems are:

- fragmented information sources
- family constraints that are hard to structure
- recommendation outputs that are hard to explain
- tools that let the model override deterministic rules

This project is intentionally designed in the opposite direction:

- **dialogue first**: complete the student dossier step by step
- **model-led recommendations**: the model produces the final recommendation draft from published knowledge and professional reasoning
- **minimal hard guardrails**: code enforces readiness, obvious conflict checks, and auditability instead of acting as the main recommender
- **governed knowledge first**: the online runtime reads only published knowledge
- **source traceability first**: every recommendation item must point back to source records

### Architecture

The repository follows a dual-runtime shape:

- **online runtime**
  - dialogue state machine
  - dossier completion
  - published knowledge retrieval
  - model-led recommendation synthesis
  - fallback / guardrail recommendation core

- **offline knowledge operations**
  - source collection
  - policy and charter extraction
  - diff detection
  - review task generation
  - promotion from reviewed records to published knowledge

Phase 1 implements the **online MVP shell**. Offline operations will expand later.

### Current Capabilities

- single pilot province: `henan`
- single cycle: `2026`
- dialogue-driven dossier completion
- structured `reach / match / safe` buckets
- recommendation trace with source IDs
- compare surface scaffold
- family-summary export scaffold
- strict separation between published and draft knowledge

### Technology Choices

- frontend: Next.js
- backend: FastAPI
- online orchestration: typed state machine
- model access: Ark Coding Plan OpenAI-compatible endpoint
- current default model: `minimax-m2.5`
- data layer: PostgreSQL as target shape, SQLite fallback for development
- license: MIT

### Intended Deployment Experience

This repository is meant to become a deployable Web product, not a local-shell-only demo.

After deployment, a user should be able to:

- open the homepage and start the assistant immediately
- complete a student dossier through guided conversation
- receive a structured shortlist once enough information is available
- inspect fit reasons, risk warnings, and source details
- compare school-program options
- export a family discussion summary

### Runtime Configuration

The live model integration targets Ark Coding Plan:

- Base URL: `https://ark.cn-beijing.volces.com/api/coding/v3`
- Model: `minimax-m2.5`
- Auth: Ark API Key

Important:

- the Coding Plan endpoint must be used
- `https://ark.cn-beijing.volces.com/api/v3` should not be used here
  because that would bypass Coding Plan quota usage and may incur extra cost

### Repository Layout

- `apps/web`: product-facing Web shell
- `services/api`: online workflow, APIs, and recommendation orchestration
- `packages/types`: shared contracts and schemas
- `packages/recommendation-core`: deterministic recommendation logic
- `packages/knowledge`: published and draft knowledge layers
- `tools/ingestion`: offline ingestion and promotion helpers
- `docs`: architecture, contracts, governance, and collaboration rules

### License Choice

This repository uses the **MIT License**.

Why MIT:

- low-friction for open collaboration
- simple and widely understood
- compatible with both personal and commercial reuse
- suitable for a fast-moving product prototype

If needed later, code licensing can remain MIT while data assets, branding, and governed knowledge content follow stricter repository policies.
