# Source relevance scoring contract

## Scope

对待整理资料进行相关性分析，推荐最接近的知识库主题，并持久化评分结果。本阶段只提供建议，不自动忽略、删除或接受任何资料。基础路径为 `/api/v1`。

## Signatures

| Boundary | File |
| --- | --- |
| HTTP routes | `backend/app/api/routes/source_documents.py` |
| scoring service | `backend/app/services/relevance_scoring.py` |
| embedding connector | `backend/app/integrations/embedding.py` |
| response schemas | `backend/app/schemas/source_document.py` |
| persistence models | `backend/app/models/source_document.py`, `backend/app/models/topic.py` |
| database migration | `backend/alembic/versions/20260924_0004_relevance_scoring.py` |

```text
POST /source-documents/score-pending
POST /source-documents/{source_document_id}/score
```

Python service signatures:

```python
score_source_document(
    session: Session,
    source_document_id: int,
    connector: EmbeddingConnector,
    settings: Settings,
) -> SourceDocumentRead

score_pending_sources(
    session: Session,
    connector: EmbeddingConnector,
    settings: Settings,
) -> SourceScoreBatchResult
```

环境变量：

| Key | Default | Rule |
| --- | --- | --- |
| `EMBEDDING_API_URL` | empty | OpenAI-compatible endpoint；为空时使用本地关键词回退 |
| `EMBEDDING_API_KEY` | empty | 只由后端读取，不得返回浏览器 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 连同向量写入缓存标识 |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | 范围 `(0, 120]` |
| `RELEVANCE_THRESHOLD` | `0.6` | 范围 `[0, 1]` |
| `RELEVANCE_BATCH_SIZE` | `20` | 范围 `[1, 100]` |

## Contracts

单条评分返回完整 `SourceDocumentRead`，包含：

```json
{
  "relevance_score": 0.86,
  "relevance_passed": true,
  "suggested_topic_id": 2,
  "relevance_method": "embedding",
  "relevance_reason": "语义上与…最接近。",
  "processing_status": "scored",
  "processed_at": "2026-09-24T02:00:00Z"
}
```

批量评分仅选取 `status=pending` 且 `processing_status in (unscored, failed)` 的资料，最多处理 `RELEVANCE_BATCH_SIZE` 条：

```json
{
  "requested": 3,
  "scored": 2,
  "failed": 1,
  "embedding": 2,
  "keyword": 0,
  "passed": 1,
  "threshold": 0.6
}
```

- 向量模式用主题所属领域和主题名称/说明构建主题语义档案，以余弦相似度排序。
- 主题和资料向量按 `model + input_hash` 缓存；对应文本或模型变更时重新计算。
- 未配置向量端点时，使用支持中文 n-gram 的本地关键词分数，`relevance_method=keyword`。
- `relevance_passed` 仅表示分数是否达到阈值；资料仍由用户决定接受或忽略。
- 来源标题或正文变化时，必须清空旧向量和分析结果，并回到 `unscored`。
- 主题候选集合或领域/主题语义变更时，必须使相关主题向量和已存评分失效；资料内容向量可继续复用。

## Validation and error matrix

| Condition | Required result |
| --- | --- |
| 资料不存在 | `404 not_found` |
| 没有可用主题 | `409 conflict`，不写入虚假建议 |
| 向量端点超时/断网 | 单条接口返回 `502 upstream_unavailable` |
| 向量数量、索引或维度非法 | `502 upstream_invalid_response` |
| 批量中某条评分失败 | 记录该条 `processing_status=failed` 和原因，继续处理其他条目 |
| 批量无待分析资料 | `200`，所有计数为 `0` |
| 向量端点未配置 | 不报错，自动使用 `keyword` |

## Good / Base / Bad

- Good: 向量返回有效结果，资料获得分数、通过标记和建议主题，再次分析复用主题向量。
- Base: 未配置外部向量服务，中文关键词回退仍产生可解释的建议。
- Bad: 外部服务返回 NaN、空向量或错误维度，后端拒绝持久化该结果。
- Bad: 低分资料被自动设为 `ignored`、删除或隐藏。

## Tests required

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

`backend/tests/test_relevance_scoring_api.py` 必须断言：

- 配置的 OpenAI-compatible 端点能够推荐主题、写入分数并缓存主题向量。
- 端点未配置时走本地关键词路径，不发起外部 HTTP 请求。
- 批量中的上游故障会记录为 `failed`，资料仍保持 `pending`。
- 连接器按响应 `index` 重排向量，并拒绝无限数、数量不等或维度不一致的响应。
- 主题新增、修改、删除或领域语义变更后，旧评分回到 `unscored` 且不再引用旧建议主题。

## Wrong vs correct

### Wrong

```python
if score < threshold:
    document.status = "ignored"
```

阈值在真实数据上尚未校准，自动忽略会把误判放大为资料丢失。

### Correct

```python
document.relevance_score = score
document.relevance_passed = score >= threshold
document.suggested_topic_id = best_topic.id
document.status = "pending"
```

将评分和建议持久化，但保留人工最终决策。
