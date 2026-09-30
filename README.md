# Knowledge Review System

A personal knowledge-review application that organizes learning into Category, Topic, and
KnowledgePoint records. The repository includes the deployable Phase 1 foundation plus the first
source-ingestion vertical slices: private notebook sync, RSS/RSSHub subscriptions, optional
Crawl4AI page cleaning, a manual source inbox, content-hash deduplication, and provenance.
The source inbox can also score pending material against the configured knowledge topics and
preselect the closest topic for manual review.
An optional OpenAI-compatible language model can turn a selected source into a structured draft;
drafts remain separate from the knowledge base until the user reviews and approves them.
Approved knowledge has a full detail/editor page and reusable questions. Daily review saves
answers and self-assessments, resumes unfinished sessions, and schedules the next review with
transparent L1–L5 rules. No model is called while practicing.

## Daily workflow

1. `/sources`: choose a source and topic, then generate or resume its draft.
2. `/drafts`: expand the original text, edit the summary/questions, save or explicitly approve.
3. `/knowledge/detail?point=ID`: read the reviewed content, trace its source, or edit questions.
4. `/review`: answer first, reveal the reference answer, then self-rate. Progress and recent
   completed sessions are stored in the database. Existing points without questions can be
   edited manually to add up to five questions.

Regeneration requires an explicit overwrite confirmation. Revision checks reject stale edits;
source changes during generation discard the generated result. See `docs/review-release.md`
for verification, backup, deployment and rollback details.

## Architecture

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic
- Database: PostgreSQL
- Local/runtime orchestration: Docker Compose

See `docs/architecture.md`, `docs/database-schema.md`, `docs/api-design.md`, and
`docs/development-roadmap.md` for the detailed contracts.

## Start with Docker

```bash
cp .env.example .env
docker compose up --build
```

After setting a random `CRAWL4AI_API_TOKEN`, start the optional self-hosted ingestion services
with:

```bash
docker compose --profile ingestion up --build
```

Open the frontend at `http://localhost:3000`, the API documentation at
`http://localhost:8000/docs`, and the health endpoint at `http://localhost:8000/health`.

## Backend development

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Frontend development

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` when the API is not using the default
address. This is a build-time public value, so rebuild the frontend image after changing it.

## Environment variables

- `POSTGRES_PORT`, `BACKEND_PORT`, and `FRONTEND_PORT`: host ports published by Docker Compose.
- `DATABASE_URL`: SQLAlchemy PostgreSQL URL used only by the backend.
- `CORS_ORIGINS`: comma-separated browser origins allowed to call the API.
- `NEXT_PUBLIC_API_BASE_URL`: public API base embedded in the frontend build.

Secrets must never use the `NEXT_PUBLIC_` prefix.

The notebook source connector uses `NOTEBOOK_API_URL`, `NOTEBOOK_API_TOKEN`, and the optional
`NOTEBOOK_TIMEOUT_SECONDS`. The service token is backend-only. The matching notebook export
extension is documented in `deploy/notebook-export/README.md`.

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
only after the user clicks “生成 AI 草稿”. `LLM_TIMEOUT_SECONDS`, `LLM_MAX_SOURCE_CHARS`, and
`LLM_MAX_OUTPUT_TOKENS` bound the request. Generation never accepts a source automatically.

## Adding future adapters

Future `MediaCrawler`, `NotificationAdapter`, and additional LLM provider implementations will live
behind backend service interfaces. Application routes will call those interfaces rather than a
vendor SDK directly.
