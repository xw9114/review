# Single-user review contract

- Routes delegate to `services/reviews.py`; schemas and frontend types must match.
- An active session is resumed, not replaced. Unique active key is the database invariant.
- Select due active knowledge only; explicit point practice may be early. Maximum ten points,
  five validated questions each. Legacy points without questions are skipped.
- Snapshot questions/answers at session creation. Do not expose answers until reveal.
- Lock the session before reveal/rating. Exact retries are idempotent; conflicting retries 409.
- Schedule a point only after all its questions are rated, using its weakest rating once.
- Again: L1 / 10 minutes. Hard: down one level / 1 day. Good: up one. Easy: up two.
  Cap at L5; L2–L5 intervals 3/7/14/30 days. This is a fixed rule, not an adaptive algorithm.
- Changed quiz hashes reset effective progress; answers to old snapshots cannot advance new quizzes.
- Point deletion preserves item snapshots with a nullable FK. Progress is deleted by cascade.
- Today's answer count uses Asia/Shanghai; stored production timestamps are timezone aware.
- Test both SQLite unit coverage and PostgreSQL release verification, including simultaneous
  session starts and identical answer submissions. Never use production learning data for QA.
