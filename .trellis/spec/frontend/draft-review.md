# AI draft review UI contract

## Scope

`/sources` 的手动生成入口和 `/drafts` 的人工审核界面。

## Signatures

| Concern | File |
| --- | --- |
| source action | `frontend/src/components/source-inbox.tsx` |
| review component | `frontend/src/components/draft-review.tsx` |
| review styles | `frontend/src/components/draft-review.module.css` |
| route | `frontend/src/app/drafts/page.tsx` |
| types/client | `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts` |

```ts
draftApi.list(): Promise<KnowledgeDraft[]>
draftApi.generate(sourceDocumentId: number, topicId: number): Promise<KnowledgeDraft>
draftApi.update(id: number, body: KnowledgeDraftReview): Promise<KnowledgeDraft>
draftApi.approve(id: number, body: KnowledgeDraftReview): Promise<KnowledgeDraft>
draftApi.reject(id: number): Promise<KnowledgeDraft>
```

## Contracts

- 资料页必须先有主题选择才启用“生成 AI 草稿”；成功后跳转 `/drafts?draft={id}`。
- 审核页显示来源、模型、提示词版本和生成次数。
- 来源仍为 pending 时 draft/rejected 可编辑；approved 只读并提供知识详情链接；stale 只读但可显式重新生成。
- 展开原文按需读取；已有草稿直接继续审核，不隐式覆盖。重新生成前确认，提交 revision 防止覆盖其他页面的修改。
- 展开原文显示字数、疑似摘要和 AI 输入上限提示；原文哈希与草稿输入不符时明确提示，并提供前往资料页补充正文的入口。
- 切换草稿/筛选、点击站内链接、关闭或刷新页面前，对未保存编辑给出提示。
- 批准与退回必须二次确认；保存只更新草稿。
- 标题、摘要、主题、至少一个要点和一道完整问答未填好时，保存/批准禁用。

## Validation and error matrix

| Condition | UI behavior |
| --- | --- |
| LLM 未配置/502 | 资料页显示后端错误，保留用户当前主题和编辑内容 |
| 草稿列表为空 | 显示前往资料收件箱的引导 |
| 批准名称冲突 | 保留全部本地编辑内容并显示 409 消息 |
| 草稿 stale | 禁用所有编辑/批准，显示重新生成链接 |
| mutation 进行中 | 禁用同一审核页的其他 mutation |

## Good / Base / Bad

- Good: 从资料页生成，跳转审核，编辑两道题后批准入库。
- Base: 保存一份草稿后离开，再打开时继续审核。
- Bad: 点击生成后直接创建知识点。
- Bad: 已批准或过期草稿仍显示可编辑表单。

## Tests required

```powershell
cd frontend
npm run lint
npx tsc --noEmit
$env:NEXT_TELEMETRY_DISABLED="1"; npm run build
node ..\docs\visual-qa\check-drafts.cjs
```

- 断言 `/drafts` 生产构建成功。
- 桌面/手机、明/暗四种截图均无横向溢出和 console error。
- 断言主题预选、要点数量、题目数量、批准按钮和导航高亮。
- 手工验证未配置 LLM 时错误横幅可关闭，资料表单内容不丢失。

## Wrong vs correct

### Wrong

```tsx
await draftApi.generate(sourceId, topicId);
await sourceApi.acceptDocument(sourceId, generated);
```

生成成功不等于人工批准。

### Correct

```tsx
const draft = await draftApi.generate(sourceId, topicId);
router.push(`/drafts?draft=${draft.id}`);
```
