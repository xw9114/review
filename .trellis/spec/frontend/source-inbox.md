# Source inbox UI contract

## Scope

资料收件箱页面 `/sources`、相关 TypeScript 类型和 API 客户端。

实现入口：

| Concern | File |
| --- | --- |
| route shell | `frontend/src/app/sources/page.tsx` |
| interactive inbox | `frontend/src/components/source-inbox.tsx` |
| inbox state/network orchestration | `frontend/src/components/sources/use-source-workspace.ts` |
| queue, relevance, decision panels | `frontend/src/components/sources/source-queue.tsx`, `source-relevance.tsx`, `source-actions.tsx` |
| status, filtering and URL helpers | `frontend/src/lib/source-workspace.ts` |
| safe rich-text rendering | `frontend/src/components/source-content.tsx` |
| API client | `frontend/src/lib/api.ts` (`sourceApi`) |
| shared types | `frontend/src/lib/types.ts` (`SourceDocument`, `SourceSyncResult`) |
| visual contract | `frontend/src/components/source-inbox.module.css` |

## Behavior

- 首次加载并行读取资料、领域和主题。
- 顶部“同步日序”按钮显式触发同步；页面加载不自动向日序发请求。
- 顶部“分析待整理”按钮显式触发批量相关性分析；页面加载不自动发送资料给向量服务。
- 状态筛选支持待整理、已整理、已忽略和已失效。
- 待整理资料可以选择领域和主题，编辑知识点名称与描述后接受。
- 忽略操作需要确认；成功后重新读取服务器状态。
- mutation 期间禁用相关按钮，错误通过可关闭横幅展示。
- 空列表、加载中和 API 离线必须有不同视觉状态。
- 详情正文按 Markdown/GFM 渲染，并通过 KaTeX 显示 `$...$`、`\(...\)`、`\[...]` 和常见
  `\begin{equation|align|gather|multline}` 数学环境。
- 不启用原始 HTML 解析，RSS 内容中的 HTML 不得直接注入 DOM；正文链接在新标签页打开。
- 对清洗后丢失标记的短中文章节名可做保守的小标题恢复，正文编辑框仍保留原始文本。
- 知识点描述默认显示渲染后的预览，可切换到编辑模式修改 Markdown/LaTeX 源码；切换资料时恢复预览模式。
- 左侧资料摘要必须去除 Markdown 装饰和 LaTeX 源码，独立或行内公式统一显示为“〔公式〕”。
- 已分析资料在列表显示百分比，详情显示方法、推荐主题和解释；打开该资料时自动选中推荐领域/主题。
- 未分析和分析失败必须是可区分状态，并提供单条分析/重试入口。
- 相关性未达阈值不得自动忽略资料，接受与忽略仍由用户操作。
- 待整理资料可在当前手动选定的主题下生成 AI 草稿；生成成功跳转草稿审核页，不直接入库。

## Type contract

`SourceDocument` 字段必须与后端 read schema 一致：`id`、`feed_source_id`、`provider`、
`source_name`、`external_id`、`title`、`content`、`content_hash`、`status`、
`source_created_at`、`last_seen_at`、`source_url`、`author`、`knowledge_point_id`、
`relevance_score`、`relevance_passed`、`suggested_topic_id`、`relevance_method`、
`relevance_reason`、`processing_status`、`processed_at`、`created_at`、`updated_at`。

客户端调用签名：

```ts
sourceApi.syncNotebook(): Promise<SourceSyncResult>
sourceApi.scorePending(): Promise<SourceScoreBatchResult>
sourceApi.scoreDocument(id: number): Promise<SourceDocument>
sourceApi.listDocuments(status: SourceStatus): Promise<SourceDocument[]>
sourceApi.acceptDocument(id: number, payload: {
  topic_id: number;
  name: string;
  description: string;
}): Promise<SourceDocument>
sourceApi.ignoreDocument(id: number): Promise<SourceDocument>
```

## Validation and error matrix

| Condition | Required UI behavior |
| --- | --- |
| 初次读取中 | 列表显示 skeleton，详情区不得渲染旧选择 |
| API 读取失败 | 显示可关闭错误横幅，不清空用户已输入的编辑内容 |
| 没有领域 | 显示前往知识库的引导，不渲染无效提交表单 |
| 当前领域没有主题 | 主题选择显示“请先创建主题”，提交按钮禁用 |
| 名称为空或 mutation 中 | 接受按钮禁用 |
| 描述为空且处于预览模式 | 展示引导切换到编辑的空状态，不渲染空白正文 |
| 同步成功 | 显示 created/updated/unchanged/stale 统计并回到 pending |
| 批量分析成功 | 显示 requested/scored/failed/embedding/keyword/passed 统计并刷新当前列表 |
| 分析完成且有推荐主题 | 自动选中对应领域和主题，但不自动提交知识点 |
| 分析失败 | 显示后端原因和重试按钮，保留资料与用户编辑内容 |

## Good / Base / Bad

- Good: 同步后选择主题并接受，资料移动到“已整理”。
- Good: 分析后显示分数和可解释的主题建议，接受表单自动预选该主题。
- Base: 没有资料时提示用户先同步日序。
- Bad: 连接器未配置时保留现有列表并显示后端错误消息。
- Bad: 接受发生名称冲突时保留用户输入和当前选择。

## Tests required

运行：

```powershell
cd frontend
npm run lint
$env:NEXT_TELEMETRY_DISABLED="1"; npm run build
node ..\docs\visual-qa\check-sources.cjs
```

断言点：

- lint 不允许在 effect 主体内同步初始化派生 state；资料选择和领域变化由事件处理器更新。
- Next 生产构建必须成功生成 `/sources`。
- 桌面/移动、明/暗四种截图均为 HTTP 200、无横向溢出、无 console error。
- 富文本截图夹具必须至少包含一个行内公式、一个独立公式和一个纯文本章节名；断言
  `.katex` 已生成且章节名恢复为 `h2`。
- 描述区默认处于预览模式并正常渲染公式；左侧摘要不得出现 `$` 或反斜杠公式源码。
- 手工错误态验证必须覆盖连接器 503，且页面仍可关闭错误横幅和切换状态。
- 截图夹具必须覆盖 scored/unscored/failed 三种分析状态，并断言分数文案和推荐主题的自动选中。

## Source supplementation (20260926_0007)

- `source-supplement.tsx` owns candidate editor, network/error/preview states; `source-quality.tsx` is shared with draft review.
- Show current character count, origin, conservative excerpt warning, and configured AI input limit if truncated. Do not label a fetched article guaranteed complete.
- Pending RSS only: click 抓取正文预览 (no mutation/LLM), inspect Markdown/KaTeX, optionally edit, then 确认应用正文 with replacement confirmation.
- 手动补充正文 works without Crawl4AI; failed fetch does not clear active content. Candidate is 1–50,000 characters, blank disables apply.
- While candidate editor is open or a content operation runs, lock source/status selection, sync, relevance, acceptance and generation. Guard unsaved candidate against leaving; cancel discards only candidate.
- 409 keeps candidate text in editor for copying; refreshing source is required before resubmission. No silent overwrite/retry.
- 已确认补充正文 exposes latest collected text and explicit restore; RSS resync cannot replace supplement. `collected_changed` warns if upstream changed.
- Apply/restore update selected source in place. Retain independently edited knowledge description/name. Existing stale draft button is 复核旧草稿, never silent regeneration.
- Full source and preview are scroll-bounded; actions wrap at 320px; existing safe Markdown renderer is reused without raw HTML.
- `sourceApi.previewContent(id, revision): Promise<SourceContentPreview>`;
  `applyContent(id, revision, content)` and `restoreContent(id, revision): Promise<SourceDocument>`;
  `getCollectedContent(id): Promise<SourceCollectedContent>`.
- Read fields match [backend source-content contract](../backend/source-content.md).
- `docs/visual-qa/check-source-content.cjs` + `SOURCE_SUPPLEMENT_QA=1` fixture verifies preview/cancel/apply/sync/stale/regenerate/restore, guard, conflict preservation, fetch failure fallback, input budget, 1440/390/320 light/dark views. No real LLM or production writes.

## Wrong vs correct

### Wrong

```tsx
useEffect(() => {
  setDraftName(selected.title);
}, [selected]);
```

这把用户事件可以完成的派生初始化放进 effect，会多一次渲染并触发 React 19 lint。

### Correct

```tsx
function selectDocument(document: SourceDocument) {
  setSelectedId(document.id);
  setDraftName(document.title);
  setDraftDescription(document.content);
}
```

## Queue and decision structure (2026-09-27)

- `filterSources(documents, { query, provider })` filters loaded rows locally. Query searches title, source name, and author case-insensitively; provider matches the stable `provider` ID, not its display name. No request or model call occurs during filtering.
- Selection must belong to the visible filtered rows. When a filter excludes the selection, select the first match or clear the detail entirely. `rememberSource(status, id)` replaces only `status`/`source` URL parameters, preserving other parameters and hash; reload reselects the requested row if still present.
- Queue has a bounded scroll area; a selected deep-linked row is scrolled into its list viewport, without moving the whole page. The visible/total count is shown while filtering.
- A failed list/category/topic/draft read shows a retry state and no editable old detail. The editor remains in memory after a failed refresh; retries use the current status/filter/deep link. An empty successful list uses the separate empty state.
- The primary pending-source action generates or resumes a draft; draft generation still requires an explicit click, and an existing non-approved draft is opened without a second generate call. The collapsed manual section contains name, Markdown/LaTeX description, and a confirmed direct-accept action. Relevance analysis stays optional.
- Changes to manual name/description trigger a discard confirmation before selection/status changes or a filter that would replace the selection. Leaving through a normal link is guarded. Opening the source body editor is disabled while manual edits are unsaved; an open candidate body editor locks the rest of triage.
- A direct accept conflict retains manually edited fields. An accepted source is read-only. Source status and current knowledge categories/topics are never changed by filtering.

### Validation and error cases

| Case | Required result |
| --- | --- |
| Filter matches nothing | Show no-match state, clear selected source URL and detail actions. |
| Deep link points to a source absent from the status/filter | Choose first visible source or clear selection. |
| Initial API read fails | Display retry and hide old detail actions, not a successful empty queue. |
| No topic in selected category | Disable generation and direct accept. |
| Manual fields edited; user cancels switch | Keep current source, filter, URL and edits. |
| Existing stale draft | Open `/drafts?draft=<id>` for human review; no automatic regeneration. |
| Accept API returns 409 | Show error and retain manual name/description. |

Good: Find one of 107 sources, read it, select a topic, and continue an existing draft. Base: an empty queue points to feed management. Bad: allow a hidden selected source to be accepted after applying a filter.

Run `node docs/visual-qa/check-workspace-structure.cjs` with the local frontend. It uses an intercepted in-memory API, checks 107 rows, filtering, deep links, manual guards, conflicts, loading locks, draft reuse, and 1440/768/390/320px light/dark layouts without real model or database writes. Keep `check-sources.cjs` and `check-source-content.cjs` for Markdown and body supplement regression.
