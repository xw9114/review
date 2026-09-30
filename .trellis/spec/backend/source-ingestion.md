# Source ingestion API contract

## Scope

用于日序笔记同步、资料状态管理和资料转知识点。基础路径为 `/api/v1`。

## Signatures

实现入口：

| Boundary | File |
| --- | --- |
| HTTP routes | `backend/app/api/routes/source_documents.py` |
| ingestion transaction | `backend/app/services/source_ingestion.py` |
| notebook HTTP client | `backend/app/integrations/notebook.py` |
| request/response schemas | `backend/app/schemas/source_document.py` |
| source models | `backend/app/models/source_document.py`, `backend/app/models/knowledge_point_source.py` |
| database migration | `backend/alembic/versions/20260923_0002_source_ingestion.py` |
| notebook export endpoint | `deploy/notebook-export/notebook_export.py` |

```text
POST /source-connectors/notebook/sync
GET  /source-documents?status=pending|accepted|ignored|stale
GET  /source-documents/{source_document_id}
POST /source-documents/{source_document_id}/accept
POST /source-documents/{source_document_id}/ignore
```

日序内部接口：

```text
GET /internal/v1/entries?kind=note
Authorization: Bearer <NOTEBOOK_EXPORT_TOKEN>
```

数据库签名：

```text
source_documents UNIQUE(provider, external_id)
knowledge_point_sources UNIQUE(source_document_id)
knowledge_point_sources UNIQUE(knowledge_point_id, source_document_id)
```

环境变量：

| Key | Consumer | Rule |
| --- | --- | --- |
| `NOTEBOOK_API_URL` | knowledge backend | 日序站点根地址；为空表示未配置 |
| `NOTEBOOK_API_TOKEN` | knowledge backend | 服务令牌；不得返回给浏览器 |
| `NOTEBOOK_EXPORT_TOKEN` | notebook | 与知识后端令牌一致 |

## Contracts

同步返回：

```json
{"created":2,"updated":0,"unchanged":1,"stale":0,"total":3}
```

接受请求：

```json
{"topic_id":1,"name":"可编辑标题","description":"可编辑正文"}
```

`source_documents.status` 只允许 `pending`、`accepted`、`ignored`、`stale`。
唯一键为 `(provider, external_id)`。内容哈希基于标准化后的标题和正文。

## Validation and errors

| Condition | Status | Code |
| --- | ---: | --- |
| 日序连接器未配置 | 503 | `connector_not_configured` |
| 日序连接或超时失败 | 502 | `upstream_unavailable` |
| 日序返回非预期结构 | 502 | `upstream_invalid_response` |
| 资料或主题不存在 | 404 | `not_found` |
| 已接受资料再次接受 | 409 | `conflict` |
| stale 资料接受 | 409 | `conflict` |
| 非法状态过滤或请求字段 | 422 | FastAPI validation detail |

同步失败不得将已有来源标记 stale。接受资料时，知识点和来源关系必须原子提交。

## Good / Base / Bad

- Good: 两条新笔记同步后均为 pending，接受其中一条生成知识点和来源关系。
- Base: 空快照返回 total=0，并将此前仍存在于该 provider 的未接受资料标记 stale。
- Bad: 上游 500 或无效 JSON 返回稳定 502，数据库资料保持原状。
- Bad: 接受不存在的主题返回 404，不生成知识点。

## Tests required

运行：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

`backend/tests/test_source_ingestion_api.py` 必须断言：

- 首次同步创建 pending 资料；相同内容再次同步计入 `unchanged`，不产生重复行。
- 标题或正文变化后更新哈希；已接受资料重新进入 pending，关联知识点不被删除。
- accept 同时创建或更新知识点、写入来源关系并把资料设为 accepted。
- 上游断网、非法 JSON、`total` 不匹配、重复 external id 均返回 502。
- 失败同步不执行 stale 标记；成功空快照才允许把缺失资料标记 stale。

## Wrong vs correct

### Wrong

```python
# 接口返回前先清空旧资料，随后逐条写入。
session.query(SourceDocument).delete()
```

这会在上游超时或返回半截数据时丢失本地状态，也会破坏知识点来源追溯。

### Correct

```python
# 先完整获取并校验 NotebookSnapshot，再在一个事务中按
# (provider, external_id) upsert；仅对成功快照计算 stale。
snapshot = await notebook.fetch_entries()
sync_snapshot(session, provider="wechat_notebook", snapshot=snapshot)
```
