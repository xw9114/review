# Database schema

## Phase 1 entities

### categories

Top-level learning domain such as ROS2 or STM32.

- `id`: primary key
- `name`, `slug`: globally unique identifiers
- `description`: optional explanation
- `sort_order`: stable user-defined ordering
- `created_at`, `updated_at`: audit timestamps

### topics

Second-level grouping inside a category, such as QoS.

- `category_id`: required foreign key with cascade deletion
- `name`, `slug`: unique within one category
- remaining fields mirror `categories`

### knowledge_points

The core knowledge unit, such as Reliability.

- `topic_id`: required foreign key with cascade deletion
- `name`, `slug`: unique within one topic
- `description`: optional definition
- `summary`: reviewed AI or human summary
- `difficulty`: optional `beginner`, `intermediate`, or `advanced`
- `key_points`: optional JSON list of reviewed key points
- `quiz_items`: optional JSON list of question and standard-answer objects
- `is_active`: allows later deactivation without deletion
- `sort_order`, `created_at`, `updated_at`

### source_documents

Source-facing records keyed by `(provider, external_id)`. Adapters store the latest title and
content, normalized SHA-256 hash, source URL, author, original creation time, last-seen time, and
one of `pending`, `accepted`, `ignored`, or `stale`. A changed accepted source returns to
`pending`; a missing notebook entry becomes `stale` without deleting derived knowledge. Feed
windows do not stale older articles.

### feed_sources

RSS/Atom or RSSHub configuration with `source_type`, endpoint, cleaning mode, enabled state, last
sync status/error, and last-run counters. Imported documents reference this table with
`ON DELETE SET NULL`, preserving provenance even if source management changes later.

### knowledge_point_sources

Provenance link between one imported source document and its current knowledge point. Accepting a
new source creates both records in one transaction; accepting a changed source updates the linked
knowledge point.

### knowledge_drafts

One current AI draft per source document. The row stores the exact source content hash used during
generation, selected topic, validated structured content, model and prompt version, generation
count, and review timestamps. Its status is `draft`, `approved`, `rejected`, or `stale`.
`revision` is an optimistic concurrency version counter.

An approved draft may reference exactly one knowledge point. Source deletion cascades to its
draft; topic or knowledge-point deletion only clears the corresponding optional reference. A
source hash mismatch blocks approval even if a stale status update was missed.

### review_sessions / review_items / review_progress

Migration `20260926_0006` adds durable reviews. A unique nullable `active_key` allows at most one
active session. Items contain immutable question, reference-answer, title and topic snapshots,
plus the user's answer, reveal time, rating and answer time. Deleting knowledge sets the item's
knowledge-point FK to null; snapshots remain readable.

Progress is keyed by knowledge point and stores its quiz hash, L1–L5 level, review count,
last-review timestamp and next due timestamp. Progress cascades on knowledge deletion. A quiz
hash mismatch treats the point as newly due. Same-question retries do not increment counts.

Future migrations may add source versions/chunks, multi-user schedules, error analyses and
notification logs. Question content currently lives in the knowledge JSON plus review snapshots,
not a separate question bank.
