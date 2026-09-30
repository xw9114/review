# Feed sources UI contract

## 1. Scope / Trigger

订阅源管理页面 `/feeds` 及其 TypeScript 类型/API 客户端。

## 2. Signatures

```ts
feedApi.list(): Promise<FeedSource[]>
feedApi.create(payload: FeedSourceCreate): Promise<FeedSource>
feedApi.update(id: number, payload: FeedSourceUpdate): Promise<FeedSource>
feedApi.sync(id: number): Promise<FeedSyncResult>
feedApi.syncAll(): Promise<FeedSyncBatchResult>
```

## 3. Contracts

- `FeedSourceInput`: `name`, `source_type`, `endpoint`, `cleaning_mode`, `enabled`
- `FeedSource`: 输入字段加 `id`, `last_synced_at`, `last_sync_status`, `last_error`,
  `last_created`, `last_updated`, `last_unchanged`, `last_failed`, `last_cleaned`,
  `created_at`, `updated_at`
- `FeedSyncResult`: `feed_source_id`, `feed_source_name`, `created`, `updated`,
  `unchanged`, `failed`, `cleaned`, `clean_failed`, `total`
- `FeedSyncBatchResult`: `sources`, `succeeded`, `failed_sources`，同步计数合计及
  `results: FeedSyncResult[]`
- `source_type`: `rss | rsshub`
- `cleaning_mode`: `feed | auto | crawl4ai`
- rss 显示完整 URL 输入；rsshub 显示 `/route/params` 输入与路由提示。
- 卡片显示 enabled、最近同步状态/时间、最近错误和统计；停用不删除历史资料。

## 4. Validation & Error Matrix

| State | UI behavior |
| --- | --- |
| 首次加载 | 页面级 loading，不渲染空态 |
| 无订阅源 | 解释 RSS 与 RSSHub 的区别，并保留创建入口 |
| mutation/sync | 仅禁用受影响来源；同步全部时禁用全局动作 |
| API 错误 | 可关闭错误横幅，保留表单输入 |
| 最近失败 | 来源行保留错误摘要，不伪装为未同步 |
| disabled | 降低视觉权重，单独同步按钮禁用 |

## 5. Good / Base / Bad Cases

- Good: 新建 RSSHub 路由，手动同步，统计显示新增资料并可跳到收件箱。
- Base: 无来源时仍可创建普通 RSS。
- Bad: URL/路由错误显示后端消息且表单不重置。

## 6. Tests Required

- `npm run lint` 与生产构建通过并生成 `/feeds`。
- 桌面/移动、明/暗主题无横向溢出和 console error。
- TypeScript 字段与 Pydantic read schema 对齐。

执行命令：

```powershell
cd frontend
npm run lint
npm run build
cd ..
node docs/visual-qa/check-feeds.cjs
```

## 7. Wrong vs Correct

### Wrong

```tsx
<input placeholder="URL" />
```

### Correct

根据 `source_type` 显示“完整 RSS 地址”或“RSSHub 路由”，并展示可执行示例。
