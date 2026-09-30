# Knowledge Review System

A personal knowledge-review application that organizes learning into Category, Topic, and
KnowledgePoint records, then turns them into spaced-repetition practice.

- **Collect**: sync a private notebook, subscribe to RSS/RSSHub feeds, or drop material into a
  manual source inbox. Content is deduplicated by hash and can be scored against your existing
  topics to suggest the closest match.
- **Turn into knowledge**: an optional OpenAI-compatible model can draft a summary, key points,
  and quiz questions from a selected source. Drafts stay separate from the knowledge base until
  you review and explicitly approve them — nothing is written automatically.
- **Review**: answer first, then reveal the reference answer and self-rate. Progress is scheduled
  with transparent L1–L5 rules (no model call while practicing) and resumes where you left off.
- **Analyze**: a dashboard panel surfaces weak points from plain review-history counters (no model
  call), plus two explicit, reviewable actions — classify recurring wrong answers, or generate
  alternate-phrasing questions that only join your quiz bank once you approve them.

Every AI-assisted step is optional, explicit, and produces something you review before it touches
your knowledge base — see [`docs/development-roadmap.md`](docs/development-roadmap.md) for what is
implemented per phase.

## Architecture

- **Frontend**: Next.js, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Pydantic, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **Orchestration**: Docker Compose (local and production use the same images)

See [`docs/architecture.md`](docs/architecture.md), [`docs/database-schema.md`](docs/database-schema.md),
[`docs/api-design.md`](docs/api-design.md), and [`docs/development-roadmap.md`](docs/development-roadmap.md)
for the detailed contracts, and [`docs/deployment.md`](docs/deployment.md) for the VPS release,
rollback, backup, and monitoring runbook this project actually uses in production.

## Prerequisites

- **Docker** and **Docker Compose v2** (`docker compose version`) — this is the only requirement
  for the quickstart below.
- For development *without* Docker: Python 3.11+, Node.js 22+, and a local PostgreSQL 17 instance
  (or run just `docker compose up postgres` and point everything else at it).
- Ports `3000` (frontend), `8000` (backend), and `5432` (Postgres) must be free, or overridden via
  `FRONTEND_PORT` / `BACKEND_PORT` / `POSTGRES_PORT` in `.env`.

## Quickstart (Docker)

```bash
git clone https://github.com/xw9114/review.git
cd review
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: <http://localhost:3000>
- API docs (Swagger UI): <http://localhost:8000/docs>
- API health check: <http://localhost:8000/health>

### First run

The database starts empty. Before `/review` has anything to show you:

1. Open `/knowledge`, create a **Category** (e.g. "ROS2"), then a **Topic** inside it (e.g. "QoS").
2. Add a **KnowledgePoint** with a name and, manually or via the AI draft flow below, up to five
   quiz questions with reference answers.
3. `/review` will now show it as due, and the dashboard's "学习分析" panel will start tracking its
   L1–L5 progress once you complete a session.

Everything above works with **no external services configured** — the LLM draft, embedding
relevance-scoring, notebook sync, and feed ingestion features below are all optional and no-op (or
fall back to local keyword matching) until you set their environment variables.

### Optional: source ingestion services

RSS/RSSHub subscriptions can optionally have their article text cleaned by Crawl4AI. Both run as
internal-only Compose services (no host port published) behind the `ingestion` profile:

```bash
# set a random CRAWL4AI_API_TOKEN in .env first
docker compose --profile ingestion up --build
```

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head        # requires a running Postgres; DATABASE_URL defaults to localhost:5432
uvicorn app.main:app --reload
```

Run the test suite (no external services required — LLM/embedding calls are faked):

```bash
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` in the environment when the API isn't
on the default address — it's a build-time public value, so rebuild after changing it.

```bash
npm run lint        # ESLint
npx tsc --noEmit     # type-check (no separate test runner; lint + tsc are the CI gate)
```

## Project layout

```text
backend/
  app/
    api/routes/       HTTP transport and request validation only
    services/          business logic and transaction boundaries
    models/             SQLAlchemy persistence models
    schemas/            Pydantic request/response contracts
    integrations/       outbound connectors (LLM, embedding, notebook, feeds, Crawl4AI)
  alembic/versions/     one migration per schema change, applied in order
  tests/                pytest, one file per API surface
frontend/
  src/app/               Next.js routes (one folder per page)
  src/components/        page-level React components + CSS modules
  src/lib/                 typed API client (api.ts) and shared types (types.ts)
deploy/                   VPS release/rollback/backup scripts (see docs/deployment.md)
docs/                     architecture, schema, API, roadmap, and deployment references
```

## Environment variables

- `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`: host ports published by Docker Compose.
- `DATABASE_URL`: SQLAlchemy PostgreSQL URL used only by the backend.
- `CORS_ORIGINS`: comma-separated browser origins allowed to call the API.
- `NEXT_PUBLIC_API_BASE_URL`: public API base embedded in the frontend build.

Secrets must never use the `NEXT_PUBLIC_` prefix.

The notebook source connector uses `NOTEBOOK_API_URL`, `NOTEBOOK_API_TOKEN`, and the optional
`NOTEBOOK_TIMEOUT_SECONDS`. The service token is backend-only. The matching notebook export
extension is documented in [`deploy/notebook-export/README.md`](deploy/notebook-export/README.md).

Feed ingestion uses `RSSHUB_BASE_URL` for trusted RSSHub route paths and
`CRAWL4AI_API_URL`/`CRAWL4AI_API_TOKEN` for optional page cleaning. Fetch and resource bounds are
controlled by the `FEED_*` settings in `.env.example`. RSSHub and Crawl4AI are internal-only
Compose services; neither publishes a host port.

Relevance analysis uses an OpenAI-compatible embedding endpoint configured through
`EMBEDDING_API_URL`, `EMBEDDING_API_KEY`, and `EMBEDDING_MODEL`. If the endpoint is empty, the
backend falls back to local Chinese/English keyword matching. `RELEVANCE_THRESHOLD` controls the
displayed pass recommendation and `RELEVANCE_BATCH_SIZE` limits one manual batch; low-scoring
material is never discarded automatically.

AI draft generation uses `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL`. The endpoint must expose
OpenAI-compatible `POST /chat/completions` and support JSON-object responses. Source text is sent
only after you click "生成 AI 草稿" (generate AI draft) — never automatically.
`LLM_TIMEOUT_SECONDS`, `LLM_MAX_SOURCE_CHARS`, and `LLM_MAX_OUTPUT_TOKENS` bound the request. The
same connector and the same "explicit trigger, reviewable output" rule power the dashboard's
error-classification and question-variant generation.

## Daily workflow (once you have data)

1. `/sources`: choose a source and topic, then generate or resume its AI draft.
2. `/drafts`: expand the original text, edit the summary/questions, save or explicitly approve.
3. `/knowledge/detail?point=ID`: read the reviewed content, trace its source, edit questions, or
   run error analysis / generate question variants for that point.
4. `/review`: answer first, reveal the reference answer, then self-rate.

Regeneration requires an explicit overwrite confirmation. Revision checks reject stale edits;
source changes during generation discard the generated result.

## Troubleshooting

- **`alembic upgrade head` fails outside Docker**: Postgres isn't reachable yet. Start it first —
  `docker compose up postgres` — or point `DATABASE_URL` at your own instance.
- **Frontend can't reach the API**: confirm `NEXT_PUBLIC_API_BASE_URL` and the backend's
  `CORS_ORIGINS` agree on the frontend's origin, then rebuild the frontend (it's a build-time
  value, not read at runtime).
- **A feature silently does nothing**: check whether its section above lists required environment
  variables — every AI/embedding/ingestion feature is designed to no-op or fall back rather than
  error when unconfigured.

## License

[MIT](LICENSE)
