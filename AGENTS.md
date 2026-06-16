# EduGuard-AI Agent Instructions

## Mission

Bring EduGuard-AI from demo quality to a university pilot-ready version by following
`docs/production-plan.md` task by task.

Before implementing any production-plan task, read `docs/production-plan.md` in full.
Treat it as the source of truth for task scope, dependencies, design, and acceptance
criteria. If the plan conflicts with actual code, follow the actual code and document
the deviation in the task summary.

## Required Context Files

Read these files before starting implementation work or when resuming after context loss:

- `docs/production-plan.md`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/api/deps.py`
- `backend/app/services/credit_compare.py`
- `backend/app/services/warning_engine.py`
- `backend/app/services/importer.py`
- `backend/app/services/notify_dispatcher.py`
- all files in `backend/app/models/`
- `frontend/src/views/Admin.vue`
- `frontend/src/api/endpoints.ts`
- `frontend/src/router/index.ts`
- `frontend/src/views/Layout.vue`

Note: the production plan mentions `Layout.vue` as a menu registration point. In this
repo it currently lives at `frontend/src/views/Layout.vue`.

## Global Technical Decisions

- Scheduled jobs use APScheduler with PostgreSQL advisory locks. Do not introduce
  Celery, Redis, Kubernetes jobs, or another scheduler.
- Notification async delivery uses the existing `notifications` table as an Outbox.
  Do not introduce a message broker.
- Sensitive stored configuration uses `cryptography` Fernet. Ciphertext must have the
  `enc:v1:` prefix, while existing plaintext must remain readable for compatibility.
- Structured logging uses `structlog`, with request IDs bound through middleware.
- Excel export uses `openpyxl`.
- Server-side PDF generation is out of scope. Use frontend print styles and browser
  "print to PDF".
- Tests must use a real PostgreSQL test database because models use JSONB. Do not
  switch tests to SQLite.
- Alembic migrations start at `0003`; every task with DDL gets its own migration file
  named for that task.

## Project Conventions

- Backend permission checks must reuse `app/api/deps.py` `require_staff` and
  `require_admin`.
- Backend business logic belongs in `backend/app/services/`.
- New frontend API calls go through `frontend/src/api/endpoints.ts`.
- New frontend pages must be registered in `frontend/src/router/index.ts` and in the
  `frontend/src/views/Layout.vue` menu when user navigation is expected.
- Keep code style consistent with the current Pydantic, SQLAlchemy 2, FastAPI, Vue 3,
  and Element Plus patterns already in the repo.
- Do not refactor outside the active task scope.
- After T1.8, key operations introduced or modified by a task need audit logging.

## Task Order

Work strictly in task-number order and complete only one production-plan task at a
time.

- Phase 1: `T1.1 -> T1.2`; `T1.3` through `T1.8` may be parallel in concept but should
  still be implemented one task at a time; `T1.9` closes the phase.
- Phase 2: `T2.1 -> T2.2 -> T2.3 -> T2.4`; `T2.5 -> T2.6`; `T2.7 -> T2.8`; `T2.9`
  is independent but still waits for its turn in the selected execution sequence.
- Phase 3: `T3.1` first; `T3.2`, `T3.3`, and `T3.6` depend on it; `T3.4` depends on
  `T3.3` and `T2.6`; `T3.5` depends on `T2.6`; `T3.7` depends on `T3.6`.
- Phase 4: `T4.2` depends on `T2.8`; other phase 4 tasks may be done after their
  practical prerequisites are present.

## Definition of Done

For every completed production-plan task:

- Relevant pytest suite passes; for broad backend changes prefer
  `cd backend && pytest --cov=app`.
- DDL changes include an Alembic migration with both upgrade and downgrade.
- New APIs appear in FastAPI OpenAPI docs at `/docs`.
- Frontend tasks pass `vue-tsc` and `npm run build`.
- Key operations include audit entries after T1.8 exists.
- Each task has a separate git commit.

Use this commit message format for production-plan tasks:

```text
feat(Tx.y): concise Chinese task summary
```

Example:

```text
feat(T1.1): pytest 基础设施与核心服务单测初始化
```

## Required Task Summary

After each production-plan task, report:

- Changed files.
- How the task was verified, mapped item by item to that task's acceptance criteria.
- Any deviations from the plan and the reason.
- Commit hash and commit message when a commit was created.

If a verification step cannot be run, state the exact reason and the remaining risk.

## Verification Commands

Backend:

```bash
cd backend && pytest --cov=app
```

Frontend:

```bash
cd frontend && npm run build
```

Run `vue-tsc --noEmit` for frontend tasks. If the repo lacks a script, add one when the
active task requires frontend verification.

## Current Repository Notes

- Existing Alembic versions are `0001_initial.py` and `0002_llm_config.py`; production
  migrations should continue with `0003`.
- `backend/app/main.py` currently allows all CORS origins; T1.3 must tighten this.
- `docs/production-plan.md` may be untracked in a fresh checkout. Do not remove or
  overwrite untracked user files.
