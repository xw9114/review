# AI knowledge draft contract

## Scope

在 `source_documents` 与正式 `knowledge_points` 之间提供人工审核的 AI 草稿层。生成必须由用户显式触发，仅批准操作可改变资料状态和创建知识点。

## Signatures

| Boundary | File |
| --- | --- |
| HTTP routes | `backend/app/api/routes/knowledge_drafts.py` |
| transaction service | `backend/app/services/knowledge_drafts.py` |
| LLM connector | `backend/app/integrations/llm.py` |
| schemas | `backend/app/schemas/knowledge_draft.py` |
| persistence | `backend/app/models/knowledge_draft.py`, `backend/app/models/knowledge_point.py` |
| migration | `backend/alembic/versions/20260924_0005_ai_drafts.py` |

```text
GET   /api/v1/knowledge-drafts?status=draft|approved|rejected|stale
GET   /api/v1/knowledge-drafts/{draft_id}
PATCH /api/v1/knowledge-drafts/{draft_id}
POST  /api/v1/knowledge-drafts/{draft_id}/approve
POST  /api/v1/knowledge-drafts/{draft_id}/reject
GET   /api/v1/source-documents/{source_document_id}/draft
POST  /api/v1/source-documents/{source_document_id}/draft/generate
```

环境变量：

| Key | Default | Rule |
| --- | --- | --- |
| `LLM_API_URL` | empty | OpenAI-compatible base URL；为空时生成返回 503 |
| `LLM_API_KEY` | empty | 仅后端可见 |
| `LLM_MODEL` | empty | 必须与上游模型 ID 完全一致 |
| `LLM_TIMEOUT_SECONDS` | `90` | 范围 `(0, 300]` |
| `LLM_MAX_SOURCE_CHARS` | `12000` | 范围 `[1000, 50000]` |
| `LLM_MAX_OUTPUT_TOKENS` | `2500` | 范围 `[500, 8000]` |

## Contracts

生成请求：

```json
{"topic_id":3}
```

审核保存/批准请求：

```json
{
  "topic_id": 3,
  "title": "Adam 优化器的核心机制",
  "summary": "可编辑摘要",
  "difficulty": "intermediate",
  "key_points": ["一阶矩估计", "二阶矩估计"],
  "quiz_items": [{"question": "问题", "answer": "标准答案"}]
}
```

- `difficulty` 仅允许 `beginner|intermediate|advanced`。
- `key_points` 为 1–8 条，单条 1–300 字符；`quiz_items` 为 1–5 条。
- 每条资料最多一份当前草稿；重新生成更新该行并递增 `generation_count`。
- 草稿保存生成时的 `source_content_hash`。来源内容变更后草稿变为 `stale`，禁止批准。
- 批准在单一事务中写入/更新知识点、来源关系、草稿状态和资料状态。
- 直接接受或忽略一条拥有未批准草稿的资料时，草稿自动转为 `rejected`。
- LLM 原文放在 JSON 用户消息中，系统提示词必须明确其为不可信引用文本，禁止执行原文指令。
- OpenAI-compatible 请求使用标准 OpenAI Python User-Agent，兼容上游 Cloudflare 客户端规则。
- 默认复用现有草稿；只有 regenerate=true 显式覆盖。响应带 revision，编辑/批准/退回校验 expected_revision。
- 远程模型调用前释放数据库事务，返回后重新加锁并校验资料哈希、content_revision 及草稿版本；不覆盖等待期间的人工作业（包括原文变更后又恢复）。
- `draft-v2` 输入包含 source_total_chars/source_truncated，提示不得基于缺失推导出题。任何现有草稿（包括 stale）默认只返回，只有显式重新生成可以覆盖。
- 单进程只允许一项生成调用；不新增定时或无人值守调用。多 worker 部署需要共享任务锁。

## Validation and error matrix

| Condition | Result |
| --- | --- |
| LLM URL/model 未配置 | `503 connector_not_configured`，不创建草稿 |
| LLM 超时、断网或 HTTP 错误 | `502 upstream_unavailable` |
| LLM 返回非 JSON/缺字段/字段越界 | `502 upstream_invalid_response` |
| 资料非 pending | `409 conflict` |
| 主题不存在 | `404 not_found` |
| 修改/拒绝已批准草稿 | `409 conflict` |
| 批准 stale 草稿或内容哈希不一致 | `409 conflict` |
| 批准时知识点名称冲突 | `409 conflict`，草稿/资料/知识点全部回滚 |

## Good / Base / Bad

- Good: 生成草稿，人工修改题目与答案，批准后一次性进入知识库。
- Base: 拒绝草稿，原资料仍在 pending，可以以后重新生成。
- Bad: LLM 返回看似 JSON 但没有答案；必须拒绝，不保存半成品。
- Bad: 原资料改变后仍批准旧草稿。

## Tests required

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

`backend/tests/test_knowledge_drafts_api.py` 必须断言：

- 生成不改变资料状态，重新生成复用同一 draft id 并递增计数。
- 编辑后批准保存结构化字段，建立唯一来源关系，重复批准返回 409。
- 拒绝不修改原资料状态；直接忽略资料会退回开放草稿。
- 原资料变更后草稿为 stale。
- 未配置模型和非法模型输出不产生持久化副作用。

## Wrong vs correct

### Wrong

```python
generated = llm.generate(source.content)
create_knowledge_point(generated)
source.status = "accepted"
```

AI 输出未经结构验证和人工确认，直接污染正式知识库。

### Correct

```python
content = DraftContent.model_validate(llm_json)
save_draft(content, source_content_hash=source.content_hash)
# 只在独立 approve 事务中创建知识点。
```
