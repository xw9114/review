# Feed connectors contract

## 1. Scope / Trigger

用于 RSS/Atom、RSSHub 路由、Crawl4AI 清洗、订阅源配置和 Feed 资料入库。

## 2. Signatures

```text
GET   /api/v1/feed-sources
POST  /api/v1/feed-sources
PATCH /api/v1/feed-sources/{feed_source_id}
POST  /api/v1/feed-sources/{feed_source_id}/sync
POST  /api/v1/feed-sources/sync-all
```

实现文件：

```text
backend/app/models/feed_source.py
backend/app/schemas/feed_source.py
backend/app/integrations/feed.py
backend/app/integrations/crawl4ai.py
backend/app/services/feed_ingestion.py
backend/app/api/routes/feed_sources.py
```

数据库：

```text
feed_sources UNIQUE(name)
source_documents.feed_source_id -> feed_sources.id ON DELETE SET NULL
source_documents UNIQUE(provider, external_id)
```

## 3. Contracts

创建请求：

```json
{"name":"技术博客","source_type":"rss","endpoint":"https://example.com/feed.xml","cleaning_mode":"auto","enabled":true}
```

更新请求允许上述五个字段的任意子集；服务层必须先与旧值合并，再按完整
`FeedSourceCreate` 重新校验，避免把 `source_type` 与 `endpoint` 更新成不匹配的组合。

`FeedSourceRead` 返回字段：

```text
id, name, source_type, endpoint, cleaning_mode, enabled,
last_synced_at, last_sync_status, last_error,
last_created, last_updated, last_unchanged, last_failed, last_cleaned,
created_at, updated_at
```

`FeedSyncResult` 返回字段：

```text
feed_source_id, feed_source_name, created, updated, unchanged,
failed, cleaned, clean_failed, total
```

`FeedSyncBatchResult` 额外返回 `sources`、`succeeded`、`failed_sources` 和
`results: FeedSyncResult[]`，其余计数字段为所有成功来源的合计。

RSSHub 请求的 `endpoint` 必须是 `/` 开头的路由；后端与 `RSSHUB_BASE_URL` 拼接。

环境变量：

| Key | Rule |
| --- | --- |
| `RSSHUB_BASE_URL` | 可信内部 RSSHub 根地址；默认空表示不配置 RSSHub |
| `CRAWL4AI_API_URL` | 可信内部 Crawl4AI 根地址；默认空表示只使用 Feed 正文 |
| `CRAWL4AI_API_TOKEN` | Bearer Token，不得返回浏览器 |
| `FEED_FETCH_TIMEOUT_SECONDS` | Feed HTTP 超时，默认 15 |
| `FEED_MAX_BYTES` | Feed 最大响应体，默认 5 MiB |
| `FEED_MAX_ITEMS` | 单次最新条目上限，默认 30 |
| `FEED_MAX_CRAWL_ITEMS` | 单次最多启动浏览器清洗的条目数，默认 5 |
| `FEED_AUTO_CRAWL_THRESHOLD` | auto 模式触发浏览器的正文字符阈值，默认 280 |

## 4. Validation & Error Matrix

| Condition | Status | Code / behavior |
| --- | ---: | --- |
| rss 非 HTTP(S)、私网或本机地址 | 422 | schema 或 `invalid_source_url` |
| rsshub endpoint 不是绝对路由 | 422 | validation detail |
| RSSHub/Crawl4AI 未配置 | 503 | `connector_not_configured` |
| Feed DNS/连接/超时/体积超限 | 502 | `upstream_unavailable` |
| 非 RSS/Atom 或无有效条目 | 502 | `upstream_invalid_response` |
| Crawl4AI 在 auto 模式失败 | 200 | 回退 Feed 正文，`clean_failed += 1` |
| Crawl4AI 在强制模式失败 | 200 | 跳过该条，`failed += 1` |
| 同步数据库失败 | 5xx | 整个事务回滚，保留旧资料 |

重定向后的每个 URL 必须重新执行公网地址校验。不得把 Feed 缺失条目标记 stale。

## 5. Good / Base / Bad Cases

- Good: RSS 两条新文章同步为 pending，其中短摘要通过 Crawl4AI 得到 Markdown。
- Base: 重复同步返回 unchanged，数据库行数不变。
- Bad: Feed 指向 `127.0.0.1` 或解析到私网地址，在发出请求前拒绝。
- Bad: Crawl4AI 离线时 auto 回退，强制模式只跳过对应条目，不覆盖旧内容。

## 6. Tests Required

- CRUD 校验 rss URL 与 rsshub route。
- RSS/Atom GUID、link、hash 三层 ID 回退。
- response size、DNS 私网、重定向私网和 XML 无效错误。
- auto/feed/crawl4ai 三种清洗路径与常见 Crawl4AI 响应形态。
- 首次、重复、更新、部分失败同步断言及 Feed 不 stale 断言。
- Alembic 从空库升级到 head。

执行命令：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\alembic.exe upgrade head
```

## 7. Wrong vs Correct

### Wrong

```python
await client.get(user_supplied_url, follow_redirects=True)
```

这允许 SSRF，且重定向可以绕过最初的主机校验。

### Correct

```python
url = validate_public_http_url(user_supplied_url)
response = await fetch_with_validated_redirects(url, max_bytes=settings.feed_max_bytes)
```
