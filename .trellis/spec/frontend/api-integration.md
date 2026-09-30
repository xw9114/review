# Knowledge API integration contract

## Scenario: Knowledge hierarchy management UI

### 1. Scope / Trigger

Use this contract when changing `src/lib/api.ts`, `src/lib/types.ts`, the dashboard totals, or
`src/components/knowledge-manager.tsx`.

### 2. Signatures

```ts
knowledgeApi.listCategories(): Promise<Category[]>
knowledgeApi.createCategory(body): Promise<Category>
knowledgeApi.updateCategory(id, body): Promise<Category>
knowledgeApi.deleteCategory(id): Promise<void>
```

Topics and knowledge points follow the same four-method pattern and include their parent ID.

### 3. Contracts

`NEXT_PUBLIC_API_BASE_URL` is a build-time browser value ending in `/api/v1`. It contains no
secret. `request<T>` sends JSON, decodes success JSON, treats `204` as `undefined`, and converts
backend error envelopes or validation details into a user-facing `Error`.

`KnowledgeManager` loads all three lists together. Category selection filters Topics; the valid
Topic selection filters KnowledgePoints. After a mutation it reloads server state instead of
assuming a local optimistic result.

The knowledge workspace uses a domain rail, topic tabs, and a knowledge-point list. Editors
open on demand. Search and the notes-only filter operate within the selected topic. New
categories/topics become selected after creation. Category/topic names are capped at 120
characters; knowledge-point names are capped at 160, matching backend schemas.

`/knowledge?category=ID&topic=ID&point=ID#knowledge-point-ID` selects the valid hierarchy and
focuses the requested point after loading. `#knowledge-search` focuses the topic search field;
`?new=category#new-category` opens the category editor.

### 4. Validation & Error Matrix

| State | UI behavior |
| --- | --- |
| Empty hierarchy | Helpful empty text; child editors disabled |
| Initial request pending | Loading placeholders; new record controls disabled |
| Mutation pending | Editor controls disabled to prevent duplicate submission |
| API error | Visible dismissible banner with decoded message |
| Delete | Browser confirmation states that descendants are deleted |
| API offline on dashboard | Totals show em dash and `API 尚未连接` appears |
| Initial knowledge API offline | Unavailable state with retry; no false empty onboarding or new writes |

### 5. Good / Base / Bad Cases

- Good: create Category, select it, create Topic, then create KnowledgePoint.
- Base: first visit with no records shows three ordered empty states.
- Bad: duplicate name returns a conflict banner and preserves the entered draft.
- Bad: deleting the active Category reloads data and selects the next available Category.

### 6. Tests Required

- `npm run lint` must report zero errors.
- `NEXT_TELEMETRY_DISABLED=1 npm run build` must type-check and prerender `/` and `/knowledge`.
- Manual browser QA must cover desktop and mobile widths when browser control is available.
- Cross-layer verification must compare TypeScript fields with Pydantic read schemas.

### 7. Wrong vs Correct

#### Wrong

```ts
fetch("http://localhost:8000/api/v1/categories");
```

#### Correct

```ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
knowledgeApi.listCategories();
```

Keep URL construction and error decoding in `src/lib/api.ts`; components consume typed methods.
