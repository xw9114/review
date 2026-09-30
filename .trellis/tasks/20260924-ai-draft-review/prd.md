# AI 知识点草稿与人工审核闭环

## Goal

在资料收件箱与正式知识库之间增加可追溯的 AI 草稿层：用户手动触发生成，编辑审核后再批准入库，AI 不得自动发布。

## What I already know

- 现有资料收件箱已支持人工主题选择、相关性建议、手动接受和来源追溯。
- 用户明确要求保持人工最终确认。
- 未配置强模型 API，因此功能必须支持“就绪但未配置”的稳定错误态。

## Requirements

- 仅待整理资料可手动触发草稿生成，请求必须带有用户当前选择的主题。
- OpenAI-compatible Chat Completions 连接器生成严格 JSON：知识点名称、摘要、难度、核心要点、题目与标准答案。
- 草稿独立持久化，记录模型、提示词版本、生成次数和时间。
- 每条来源只有一份当前草稿；重新生成覆盖当前未批准内容并增加计数。
- 草稿审核页支持修改主题、名称、摘要、难度、要点、题目和答案，以及保存、拒绝、批准。
- 批准必须原子创建知识点、来源关系，更新资料和草稿状态。
- 正式知识点保存结构化摘要、难度、要点和测试题，供后续复习复用。
- 原文、API Key 和草稿均不通过公开端口暴露；API Key 只在后端环境变量中存在。

## Acceptance Criteria

- [ ] 未配置 LLM 时生成返回稳定 503，资料仍为 pending。
- [ ] 无效 JSON、字段越界或网络失败不创建/覆盖草稿。
- [ ] 生成成功保存草稿与模型元数据，重新生成增加 generation_count。
- [ ] 审核编辑和拒绝不改变原始资料状态。
- [ ] 批准后草稿为 approved、资料为 accepted，知识点可追溯到唯一来源。
- [ ] 已批准草稿不可重新修改、拒绝或生成。
- [ ] 后端测试、迁移、前端 lint/typecheck/build 和草稿页视觉回归通过。

## Definition of Done

- 数据库迁移、模型连接器、服务、API、审核页、Compose 配置和 code-spec 同步。
- 部署前备份生产数据库，迁移与旧数据兼容，可回滚。

## Technical Approach

- 新增 `knowledge_drafts` 表，对 `source_document_id` 唯一，JSON 字段保存要点与题目。
- 扩展 `knowledge_points` 保存 `summary/difficulty/key_points/quiz_items`。
- 连接器使用 `POST /chat/completions` + `response_format=json_object`，Pydantic 做第二次严格验证。
- 审核使用独立 `/drafts` 页面；资料页仅负责选主题和发起生成。

## Decision (ADR-lite)

**Context**: AI 输出可能错误，且用户要求保持手动确定。

**Decision**: 草稿与正式知识点分层持久化；生成、保存、批准是三个显式操作，只有批准会改变资料状态。

**Consequences**: 流程多一步，但可审计、可编辑，并为未来人工反馈和提示词迭代保留边界。

## Out of Scope

- 自动批量生成、自动批准或低分自动丢弃。
- 多用户权限、草稿历史版本列表、消息队列、定时生成。
- 模型微调、Reranker 和自动阈值校准。
