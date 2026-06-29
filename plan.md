# OfferFlow 开发计划

> 面试诊断 Agent — 上传文字稿 → 拆分为面试回合 → 逐回合诊断 → 输出结构化改进建议
>
> 架构：Harness 10层手写引擎 + FastAPI + Vue 3

## 状态说明

- ✅ 已完成
- 🚧 进行中
- ⬚ 待开始

---

## Phase 0 — Git 初始化 + 项目脚手架 ✅

- [x] `git init`，创建 `.gitignore`
- [x] 首次 commit：CONTEXT.md + docs/adr/ + .gitignore
- [x] `git remote add origin https://github.com/oceanphy/OfferFlow.git`
- [x] 创建 `backend/` 目录结构，用 `uv init` 初始化项目
- [x] `uv add fastapi uvicorn[standard] openai pydantic httpx` 安装依赖
- [x] 创建最小 FastAPI app：`GET /health` 返回 `{"status": "ok"}`
- [x] 创建 `frontend/` Vue 3 + Vite 脚手架
- [x] `git push -u origin main`

---

## Phase 1 — L1: Tools 原子能力 ⬚

- [ ] 定义 `ToolProtocol`：`name`, `description`, `parameters` (JSON Schema), `execute(**kwargs) -> ToolResult`
- [ ] `ToolResult` 数据类：`success`, `data`, `error_type` (input_error/service_error/timeout), `audit_log`
- [ ] 实现 `split_rounds`：输入全文 → 输出 `list[InterviewRound]`
- [ ] 实现 `analyze_content`：输入单轮 Q&A + 证据源 → 输出内容诊断结果
- [ ] 实现 `query_knowledge_base`：输入问题文本 → 输出匹配的知识库条目
- [ ] 实现 `generate_report`：输入所有回合诊断摘要 → 输出完整诊断报告（Markdown）
- [ ] 审计日志机制
- [ ] 单元测试

---

## Phase 2 — L3: Query Engine 模型调用层 ⬚

- [ ] `LLMClient`：封装 OpenAI-compatible API 调用（流式/非流式/重试/降级）
- [ ] `TokenBudget`：每次调用设定 token 上限
- [ ] `ResponseCache`：相同输入的 LLM 结果缓存
- [ ] 将 `analyze_content` 接入 LLMClient，prompt 模板化
- [ ] 端到端测试：拿 demo 文字稿跑一次完整诊断流程

---

## Phase 3 — L4: Context 上下文管理 ⬚

- [ ] 分层注入结构：system_prompt / current_task / reference / history
- [ ] 自动压缩策略
- [ ] Context 窗口监控

---

## Phase 4 — L10: Sub-agent 并行分发 ⬚

- [ ] `SubAgent` 协议
- [ ] 四个 sub-agent 实现：ContentDiagnosis / ExpressionDiagnosis / KnowledgeBenchmarking / ReportGeneration
- [ ] `AgentOrchestrator`：并行分发 + 超时控制 + 结果聚合
- [ ] Sub-agent 上下文隔离

---

## Phase 5 — L2: Skills 任务编排 + API 层 ⬚

- [ ] `SkillProtocol`：`name`, `pipeline`, `lifecycle`
- [ ] 核心 Skill `diagnose_transcript`
- [ ] FastAPI routes：`POST /api/diagnose` (SSE), `GET /api/report/{id}`

---

## Phase 6 — Frontend MVP ⬚

- [ ] 上传页面：粘贴文字稿 / 上传文件
- [ ] 诊断进度页：SSE 流式展示诊断进度
- [ ] 报告展示页：Markdown 渲染

---

## Phase 7 — L5+L6+L7: Memory + Permission + Sessions ⬚

- [ ] L5 Memory：UserProfile / DiagnosisHistory / SessionContext
- [ ] L7 Sessions：中断恢复
- [ ] L6 Permission：数据删除 API、模型调用不附带用户身份

---

## Phase 8 — L8+L9: Command + Hook ⬚

- [ ] L8 Command：CLI 入口 `offerflow diagnose <file>`
- [ ] L9 Hook：扩展点 `pre_diagnose`, `post_round`, `post_report`

---

## Phase 9 — 知识库管理 ⬚

- [ ] CRUD API：`POST/GET/PUT/DELETE /api/knowledge/entries`
- [ ] 条目结构：题目、关键词、参考答案、评分标准、常见错误
