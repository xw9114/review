# API design

Base path: `/api/v1`

## Categories

- `GET /categories`
- `POST /categories`
- `GET /categories/{id}`
- `PATCH /categories/{id}`
- `DELETE /categories/{id}`

## Topics

- `GET /topics?category_id={id}`
- `POST /topics`
- `GET /topics/{id}`
- `PATCH /topics/{id}`
- `DELETE /topics/{id}`

## Knowledge points

- `GET /knowledge-points?topic_id={id}`
- `POST /knowledge-points`
- `GET /knowledge-points/{id}`
- `PATCH /knowledge-points/{id}`
- `DELETE /knowledge-points/{id}`

AI 草稿批准后，知识点还会保存 `summary`、`difficulty`、`key_points` 和
`quiz_items`。这些字段为空时仍兼容手工创建的旧知识点。

## Source inbox

- `POST /source-connectors/notebook/sync`
- `GET /source-documents?status={pending|accepted|ignored|stale}`
- `GET /source-documents/{id}`
- `POST /source-documents/{id}/accept`
- `POST /source-documents/{id}/ignore`

Notebook sync is explicit and idempotent. It validates the whole upstream snapshot before writing
and returns counts for created, updated, unchanged, and stale records. Accept requires an existing
`topic_id`, a knowledge-point name, and an optional description.

## AI knowledge drafts

- `GET /knowledge-drafts?status={draft|approved|rejected|stale}`
- `GET /knowledge-drafts/{id}`
- `PATCH /knowledge-drafts/{id}`
- `POST /knowledge-drafts/{id}/approve`
- `POST /knowledge-drafts/{id}/reject`
- `GET /source-documents/{id}/draft`
- `POST /source-documents/{id}/draft/generate`

Generation is always manual and requires an existing `topic_id`. The AI output is validated and
stored separately from the knowledge base. Saving or rejecting a draft never accepts the source.
Approval is the only action that writes the reviewed title, summary, difficulty, key points, and
quiz answers to a knowledge point; that write, its provenance link, and the source status change
commit atomically. If the source content changes, its current draft becomes `stale` and cannot be
approved until it is regenerated.

Generate accepts `regenerate` (default false) and optional `expected_revision`. An existing
editable draft is returned without another model call unless regeneration is explicit. Read
responses include `revision` and `source_status`. Edit/approve bodies pass `expected_revision`;
reject accepts it as a query parameter. A mismatch returns 409 without overwriting saved work.
Production runs one backend worker; concurrent generation is bounded to one in-flight model call
per process. Generation releases its DB transaction while waiting for the model, then verifies
both the source hash and draft revision again before saving.

## Reviews

- `GET /reviews/overview`: due points, Shanghai-calendar-day answer count, mastery levels,
  active session ID, and the last ten completed sessions.
- `GET /reviews/active`: current session or null.
- `POST /reviews/sessions`: optional `knowledge_point_id`, `topic_id`, and `limit` (1–10,
  default 5 points). Returns an existing active session before starting another. Without a
  point ID, only due knowledge is selected; explicit point practice can be early.
- `GET /reviews/sessions/{id}`: ordered question/answer snapshots.
- `POST /reviews/items/{id}/reveal`: saves `user_answer` and reveals the reference answer.
- `POST /reviews/items/{id}/answer`: `user_answer` and `rating` (`again|hard|good|easy`).

Standard answers are null before reveal. Rating before reveal or changing an already recorded
rating returns 409; retrying the identical answer/rating is idempotent. The weakest self-rating
across all questions of a point updates its schedule only once. Quiz changes invalidate the old
schedule without altering historical question/answer snapshots. This is a single-user workflow,
protected by the existing authenticated gateway, not a multi-tenant API.

## Analysis

- `GET /analysis/overview`: mastery distribution (L1–L5 counts), up to ten weak points, the
  error-type distribution across generated analyses, and deterministic Chinese tips.
- `GET /analysis/knowledge-points/{id}/error-analysis`
- `POST /analysis/knowledge-points/{id}/error-analysis/generate`
- `GET /analysis/knowledge-points/{id}/question-variants?status={pending|approved|rejected}`
- `POST /analysis/knowledge-points/{id}/question-variants/generate` (`count`, 1–5, default 3)
- `POST /analysis/question-variants/{id}/approve`
- `POST /analysis/question-variants/{id}/reject`

The dashboard analytics, mastery distribution, and tips are computed from `review_progress`
counters alone — no model call, matching the review scheduler's transparent, deterministic
rules. Error classification and question-variant generation are the only two model-assisted
actions in this feature: both are explicit and manual, follow the same generate-then-review
lifecycle as AI knowledge drafts, and never run while practicing. A knowledge point needs at
least one `again`/`hard`-rated answer before an error analysis can be generated. Regenerating an
error analysis replaces its single stored row; regenerating question variants replaces only the
still-`pending` rows for that point. Approving a variant appends it to the point's `quiz_items`
and is the only write this feature makes to the knowledge base — identical in effect to editing
the quiz list by hand.

## Feed sources

- `GET /feed-sources`
- `POST /feed-sources`
- `PATCH /feed-sources/{id}`
- `POST /feed-sources/{id}/sync`
- `POST /feed-sources/sync-all`

Feed source type is `rss` or `rsshub`; cleaning mode is `feed`, `auto`, or `crawl4ai`. RSSHub
stores a route beginning with `/`, while RSS stores a complete public URL. Sync is manual,
bounded, idempotent, and reports import and cleaning counts.

## Errors

Domain errors use a stable envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Category not found."
  }
}
```

Validation failures retain FastAPI's standard `422` response during Phase 1.
