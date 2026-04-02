# AI-ZhangXuefeng

[中文](#中文说明) | [English](#english)

## 中文说明

### 项目是什么

`AI-ZhangXuefeng` 是一个面向普通中国家庭的高考志愿助手。

它不是“输入分数直接吐学校名单”的黑箱工具，而是一个：

- 对话驱动
- 模型主导推荐
- 知识与检索增强
- 来源可留痕
- 可持续重排

的决策产品。

### 设计哲学

- **AI 是主脑**：理解、追问、方向判断、候选发现、排序、比较和解释主要交给模型完成
- **workflow 是增强器**：负责 memory、retrieval、streaming、audit，不替模型拍板
- **知识库是高质量上下文**：`published knowledge` 是可信记忆层，不是候选边界
- **模型原生检索优先**：开放检索可用于发现候选，自控检索作为 fallback
- **最低护栏只兜底**：只处理明显冲突、明显错误和不可接受表达
- **纯聊天主界面**：用户像和顾问聊天一样推进，不走工具站路径

### 当前架构

- `apps/web`
  - 聊天主界面
  - 志愿清单 rail
  - 任务轨迹展示
  - SSE 流式消费
- `services/api`
  - session / message / stream API
  - state-machine orchestration
  - runtime promptpacks
  - recommendation / compare / refine 编排
  - 持久化
- `packages/knowledge`
  - published / draft knowledge
  - source records
- `packages/recommendation-core`
  - fallback / hint / minimum guardrail
- `packages/types`
  - 前后端共享契约
- `tools/ingestion`
  - 离线知识导入与发布脚手架

### 当前运行时形态

在线主链路已经是 AI-first 骨架：

- 用户自然语言输入
- 系统更新 dossier memory
- runtime promptpacks 驱动模型判断当前意图
- `published knowledge` + 开放检索共同提供上下文
- 模型输出方向建议、正式推荐、比较或重排结果
- recommendation 和 compare 通过 `/stream` 流式输出

### 推荐链路原则

- recommendation 不再被本地小知识库样本锁死
- 模型可以通过开放检索发现更多候选
- 推荐结果按冲 / 稳 / 保清单组织
- 高价值外部发现可自动回流到 `draft/auto-discovery`
- `recommendation-core` 只在 fallback / hint / minimum guardrail 时介入

### 运行时配置

- Base URL: `https://ark.cn-beijing.volces.com/api/coding/v3`
- Default model: `minimax-m2.5`
- Auth: Ark API Key

重要：

- 必须使用 Coding Plan 专用地址
- 不应使用 `https://ark.cn-beijing.volces.com/api/v3`

### 当前约束

- 省份试点：`henan`
- 年份试点：`2026`
- 默认用户：普通中国学生和家庭
- 默认网络环境：按中国可访问性和中文教育来源设计

### 开源协议

本仓库采用 **MIT License**。

## English

### What This Project Is

`AI-ZhangXuefeng` is a dialogue-first gaokao planning assistant for ordinary Chinese families.

It is not a score-to-school black box. It is an:

- AI-first
- chat-native
- knowledge-and-retrieval-enhanced
- source-traceable
- continuously refinable

guidance product.

### Design Philosophy

- **The model is the main reasoning engine**
- **Workflow is an enhancer, not the judge**
- **Knowledge is trusted memory, not the candidate boundary**
- **Model-native search is preferred; controlled retrieval is fallback**
- **Minimum guardrails only handle obvious risk**
- **The main product surface is chat**

### Current Architecture

- `apps/web`: chat UI, shortlist rail, task trace, SSE consumption
- `services/api`: orchestration, runtime promptpacks, streaming, persistence
- `packages/knowledge`: published and draft knowledge
- `packages/recommendation-core`: fallback / hint / minimum guardrail
- `packages/types`: shared contracts
- `tools/ingestion`: offline ingestion and promotion helpers

### Runtime Shape

The current runtime is already an AI-first skeleton:

- user speaks naturally
- system updates dossier memory
- promptpacks drive model behavior
- published knowledge plus open retrieval provide context
- model generates guidance, recommendation, comparison, or refinement
- `/stream` delivers the live user-facing experience

### License

This repository uses the **MIT License**.
