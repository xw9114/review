# Frontend visual refresh — 2026-09-22

The frontend now uses a warm neutral canvas, graphite text, lime accents, custom line
illustrations, and an editorial sidebar layout. Both light and dark themes are supported.
The knowledge editor is organized into a domain rail, topic tabs, and a searchable note list.

## Verification

- ESLint: passed.
- Production Next.js/Docker build: passed.
- Live empty-state screenshots: desktop/mobile × light/dark × dashboard/knowledge,
  eight cases passed with HTTP 200, live API reads successful, no console errors or overflow.
- Interaction scenarios: desktop 13, mobile 13, tablet navigation 1; all 27 passed.
- Interaction coverage includes create/edit/delete, confirmation cancellation, draft
  preservation after a conflict, search/filters, deep links, theme persistence, and API retry.
- Interaction data is intercepted in memory. No test records were written to the live database.

`after/` contains screenshots of the real local application and `results.json`.
`interactions/*-fixture.png` contains screenshots with explicitly simulated sample data.
The older interim expectation screenshots are diagnostic artifacts, not final failures.

Run `node docs/visual-qa/check-ui.cjs after` or
`node docs/visual-qa/check-interactions.cjs` from the project root to repeat these checks.
The scripts use the local Playwright/Chromium installation; `PLAYWRIGHT_MODULE`,
`QA_CHROMIUM_PATH`, and `QA_BASE_URL` can override their locations.
