# Multi-User Job Search Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an invite-only, strictly private multi-user job-search web application that uses each user's BOSS browser session to collect shared jobs, scores them with private profiles and preferences, and batch-generates reviewable DOCX/PDF materials.

**Architecture:** Use a modular monolith with a FastAPI REST API, React frontend, SQLite-compatible SQLAlchemy repositories, MinIO object storage, database-backed background tasks, and one Chromium Profile per user. Keep shared job facts separate from user-owned evaluations, files, profiles, drafts, and application records; expose `BrowserConnector`, `LLMProvider`, `ObjectStorage`, and `TaskRunner` interfaces so the local pilot can migrate to PostgreSQL, cloud object storage, a local browser Agent, and a durable queue.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite, PostgreSQL-compatible queries, MinIO/S3 via `boto3`, React + TypeScript + Vite, Playwright, existing crawler/ranking/material modules, and offline `unittest`/frontend tests.

## Global Constraints

- The first platform is BOSS Zhipin; other portals are not part of the first web release.
- Registration is invite-only; the first release has administrator password reset and no email recovery.
- User-private data is isolated by authenticated `user_id`; administrators do not receive a private-content browsing API.
- Public job facts may be shared; user scores, filters, notes, files, drafts, and applications must remain private.
- Users must explicitly consent before the first AI processing call and can revoke AI processing in settings.
- The administrator default model key is stored in environment configuration; a user key is encrypted at rest and takes precedence.
- Passwords are hashed; passwords, model keys, cookies, tokens, and raw document contents never enter logs or Git.
- Each user receives an independent Chromium Profile. The system never stores a BOSS password and only reads job information.
- Login expiry, CAPTCHA, SMS verification, rate limiting, anti-bot, and abnormal access responses produce `paused` task status and require user intervention.
- No platform upload, application submission, chat, reply, or other platform write operation is implemented.
- Use the existing `src/ranking_rules.py`, `src/job_schema.py`, `crawlers/boss_cdp.py`, and material helpers through adapters; do not duplicate their domain logic in HTTP routes.
- Do not install dependencies, access live BOSS, or commit/push without explicit authorization at execution time.

## Repository Map

Create a focused web application beside the current local workflow:

```text
server/
  app.py                         # FastAPI application factory
  settings.py                    # environment-backed settings
  db.py                          # SQLAlchemy engine/session
  models/                        # ORM entities and relationships
  schemas/                       # request/response DTOs
  repositories/                  # tenant-filtered data access
  services/                      # profile, job, material, task services
  adapters/                      # BOSS, LLM, MinIO, existing-domain adapters
  api/                            # authenticated route modules
  security/                       # password, invite, session, authorization
web/
  src/                            # React application
  tests/                          # frontend component and flow tests
  package.json
docker-compose.yml                # FastAPI, React, MinIO for local pilot
tests_web/                        # backend API/service tests
```

Existing local CLI behavior remains available while web services are introduced. The web layer must call shared domain functions rather than import CLI `main()` functions.

---

### Task 1: Scaffold the Web Runtime and Local Services

**Files:**
- Create: `server/app.py`, `server/settings.py`, `server/db.py`, `server/__init__.py`
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/src/main.tsx`
- Create: `docker-compose.yml`, `.env.example`
- Modify: `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `README.md`
- Test: `tests_web/test_app_health.py`

**Interfaces:**
- `create_app(settings: Settings | None = None) -> FastAPI`
- `GET /api/health -> {"status": "ok", "version": str}`
- `Settings.database_url`, `Settings.s3_endpoint`, `Settings.s3_bucket`, `Settings.default_model_key`

- [ ] **Step 1: Write the failing health and settings tests.** Assert that `create_app()` exposes `/api/health`, settings load from an injected environment mapping, and no secret value appears in the health response.
- [ ] **Step 2: Run the focused test.**

  Run: `python -m unittest tests_web.test_app_health -v`

  Expected: FAIL because the `server` package and health route do not exist.
- [ ] **Step 3: Add the FastAPI factory and settings model.** Use Pydantic settings with explicit defaults for local SQLite and MinIO; keep the default model key empty unless configured.
- [ ] **Step 4: Add Vite React bootstrap and Docker Compose.** Compose must expose FastAPI and MinIO locally, persist MinIO data under an ignored directory, and avoid putting secrets in tracked files.
- [ ] **Step 5: Run the focused test and compile checks.**

  Run: `python -m unittest tests_web.test_app_health -v`

  Expected: PASS. Then run `python -m compileall -q server`.

---

### Task 2: Add Database Models, Migrations, and Tenant Repositories

**Files:**
- Create: `server/models/base.py`, `server/models/entities.py`, `server/repositories/tenant.py`, `alembic.ini`, `alembic/`
- Create: `tests_web/test_tenant_repositories.py`
- Modify: `server/db.py`

**Interfaces:**
- `User`, `Invite`, `CandidateProfile`, `SourceDocument`, `SearchTemplate`, `Job`, `UserJobEvaluation`, `MaterialBatch`, `MaterialDraft`, `FileObject`, `Application`, `Task`, `ModelCredential`, `BrowserSession`
- `TenantRepository(session: Session, user_id: UUID)`
- `TenantRepository.get_profile() -> CandidateProfile | None`
- `TenantRepository.list_evaluations() -> list[UserJobEvaluation]`
- `TenantRepository.get_file(file_id: UUID) -> FileObject | None`
- `JobRepository.upsert_public_job(job: JobSummary) -> Job`

- [ ] **Step 1: Write isolation tests with two users.** Verify that user A cannot fetch user B's profile, file, evaluation, draft, application, task, credential, or browser session; verify both users can read the same public `Job`.
- [ ] **Step 2: Run the focused test.**

  Run: `python -m unittest tests_web.test_tenant_repositories -v`

  Expected: FAIL because the ORM entities and repositories do not exist.
- [ ] **Step 3: Implement ORM entities and constraints.** Add `user_id` to every private table, unique keys for invite tokens and public job identity, foreign keys with user ownership, timestamps, version fields, and task status fields.
- [ ] **Step 4: Implement repositories that require an authenticated user context.** Never accept an owner ID from a route body; repository methods scope all private queries to the constructor's `user_id`.
- [ ] **Step 5: Add Alembic initial migration and SQLite test fixture.** Keep column types and constraints compatible with PostgreSQL.
- [ ] **Step 6: Run tests and migration checks.**

  Run: `python -m unittest tests_web.test_tenant_repositories -v`

  Expected: PASS. Run `alembic upgrade head` against a temporary SQLite database and verify the tables exist.

---

### Task 3: Implement Invite-Only Authentication and Authorization

**Files:**
- Create: `server/security/passwords.py`, `server/security/sessions.py`, `server/security/permissions.py`
- Create: `server/api/auth.py`, `server/api/invites.py`, `server/api/admin.py`
- Create: `tests_web/test_auth_and_invites.py`, `tests_web/test_authorization.py`

**Interfaces:**
- `POST /api/auth/register {invite, username, password} -> UserView`
- `POST /api/auth/login {username, password} -> SessionView`
- `POST /api/auth/logout -> 204`
- `GET /api/auth/me -> UserView`
- `POST /api/admin/invites -> InviteView`
- `POST /api/admin/users/{user_id}/password-reset -> 204`
- `require_user(request) -> AuthenticatedUser`
- `require_admin(user) -> AuthenticatedUser`

- [ ] **Step 1: Write failing tests for one-time invitations, password hashing, session cookies, logout, disabled users, and admin-only routes.** Include a test that an ordinary user receives `403` from all admin routes.
- [ ] **Step 2: Run the focused tests.**

  Run: `python -m unittest tests_web.test_auth_and_invites tests_web.test_authorization -v`

  Expected: FAIL because authentication routes and security helpers do not exist.
- [ ] **Step 3: Implement Argon2 password hashing and opaque server-side sessions.** Store only a hash of the session token, set an HttpOnly/SameSite cookie, rotate the session on login, and invalidate sessions on password reset.
- [ ] **Step 4: Implement invitation consumption.** Require an unexpired unused invite, atomically mark it used during registration, and reject reuse or disabled accounts.
- [ ] **Step 5: Add administrator invite, account-state, and password-reset routes.** Do not add an endpoint that returns user-private content to administrators.
- [ ] **Step 6: Run the focused tests and a compile check.**

  Expected: all auth and authorization tests PASS.

---

### Task 4: Add MinIO Object Storage and Private Document Upload

**Files:**
- Create: `server/adapters/object_storage.py`, `server/services/documents.py`, `server/api/documents.py`
- Create: `tests_web/test_object_storage.py`, `tests_web/test_document_permissions.py`
- Modify: `server/settings.py`, `docker-compose.yml`

**Interfaces:**
- `ObjectStorage.put(owner_id: UUID, content: BinaryIO, content_type: str, filename: str) -> StoredObject`
- `ObjectStorage.open_for_user(owner_id: UUID, file_id: UUID) -> BinaryIO`
- `POST /api/documents -> SourceDocumentView`
- `GET /api/documents -> list[SourceDocumentView]`
- `GET /api/documents/{file_id}/download -> file response`

- [ ] **Step 1: Write tests using a fake S3-compatible storage.** Assert deterministic `users/{user_id}/...` keys, content hash capture, allowed extensions, size limits, and user A cannot download user B's object.
- [ ] **Step 2: Run the focused tests and confirm red.**

  Run: `python -m unittest tests_web.test_object_storage tests_web.test_document_permissions -v`

  Expected: FAIL because the storage adapter and document routes do not exist.
- [ ] **Step 3: Implement the MinIO/S3 adapter and metadata transaction.** Upload the object first, then commit metadata; if metadata fails, delete the exact newly-created object.
- [ ] **Step 4: Implement authenticated upload/list/download routes.** Use multipart limits, content-type checks, generated object keys, and short-lived authorized downloads.
- [ ] **Step 5: Run focused tests and MinIO integration tests when the local service is available.**

  Expected: unit tests PASS; integration tests are explicitly reported as unavailable when MinIO is not running.

---

### Task 5: Build Profile Extraction, Consent, and Confirmation

**Files:**
- Create: `server/adapters/llm_provider.py`, `server/services/profile_extraction.py`, `server/api/profile.py`, `server/api/settings.py`
- Modify: `tools/inventory_candidate_documents.py`, `tools/profile_state.py` only where shared extraction helpers are reusable
- Create: `tests_web/test_profile_extraction.py`, `tests_web/test_ai_consent.py`

**Interfaces:**
- `LLMProvider.extract_profile(source_text: str, schema: dict) -> ProfileProposal`
- `ProfileService.create_proposal(user_id: UUID, document_ids: list[UUID]) -> ProfileProposal`
- `ProfileService.confirm_proposal(user_id: UUID, proposal_id: UUID, accepted_fields: list[str]) -> CandidateProfile`
- `POST /api/profile/proposals -> ProfileProposalView`
- `POST /api/profile/proposals/{proposal_id}/confirm -> ProfileView`
- `GET/PATCH /api/settings/ai-consent`

- [ ] **Step 1: Write tests for first-use consent, revoked consent, source references, rejected changes, and profile versioning.** The tests must prove unconfirmed proposals do not mutate the confirmed profile.
- [ ] **Step 2: Run focused tests and confirm red.**

  Run: `python -m unittest tests_web.test_profile_extraction tests_web.test_ai_consent -v`

  Expected: FAIL because the web profile services do not exist.
- [ ] **Step 3: Implement local text extraction adapters.** Reuse existing PDF/DOCX/Markdown/plain-text helpers and keep the original source object referenced in each proposed fact.
- [ ] **Step 4: Implement the LLM provider boundary.** Select user credentials when enabled, otherwise the administrator default; refuse calls without consent or an available key; redact secrets from errors.
- [ ] **Step 5: Implement proposal confirmation and immutable profile versions.** Store accepted fields only and retain source references and confirmation timestamps.
- [ ] **Step 6: Run focused tests and verify no raw source content appears in ordinary task logs.**

---

### Task 6: Generalize Preferences, Scoring, and Public Job Repositories

**Files:**
- Create: `server/adapters/job_domain.py`, `server/services/evaluation.py`, `server/api/search_templates.py`, `server/api/evaluations.py`, `server/api/jobs.py`
- Modify: `src/job_schema.py`, `src/ranking_rules.py`
- Create: `tests_web/test_search_templates.py`, `tests_web/test_user_evaluations.py`, `tests_web/test_shared_jobs.py`

**Interfaces:**
- `SearchTemplateInput` with `keywords`, `cities`, `industries`, `experience`, `education`, `salary_reference`, `work_modes`, `hard_exclusions`, and `weights`
- `EvaluationService.evaluate_for_user(user_id: UUID, job_ids: list[str], template_id: UUID) -> list[UserJobEvaluation]`
- `POST /api/search-templates -> SearchTemplateView`
- `GET /api/jobs -> list[JobView]` with user-private evaluation fields joined for the current user
- `POST /api/evaluations/batch -> EvaluationBatchView`
- `PATCH /api/evaluations/{job_id} -> UserJobEvaluationView`

- [ ] **Step 1: Write tests showing two users can use different hard filters and weights against one shared job set.** Cover custom cities, arbitrary role keywords, salary as reference, exclusion reasons, and visible risk flags.
- [ ] **Step 2: Run focused tests and confirm red.**

  Run: `python -m unittest tests_web.test_search_templates tests_web.test_user_evaluations tests_web.test_shared_jobs -v`

  Expected: FAIL because the web preference and evaluation services do not exist.
- [ ] **Step 3: Move candidate-specific assumptions out of global constants.** Preserve existing single-user test behavior through a default profile/rules adapter while allowing user-provided preferences and weights.
- [ ] **Step 4: Implement public job upsert and user-private evaluation repositories.** Store only normalized public fields in `jobs`; store all user state in `user_job_evaluations`.
- [ ] **Step 5: Implement paginated job and template APIs.** Ensure a user sees only their own evaluation columns and cannot update another user's row.
- [ ] **Step 6: Run focused tests and the existing ranking suite.**

  Run: `python -m unittest tests_web.test_search_templates tests_web.test_user_evaluations tests_web.test_shared_jobs tests.test_ranking_rules -v`

  Expected: PASS with existing local workflow behavior preserved.

---

### Task 7: Implement Per-User BOSS Browser Sessions and Collection Tasks

**Files:**
- Create: `server/adapters/browser_connector.py`, `server/services/browser_sessions.py`, `server/services/job_collection.py`, `server/api/browser_sessions.py`, `server/api/collection_tasks.py`
- Modify: `crawlers/boss_cdp.py`, `crawlers/browser.py`, `crawlers/access_guard.py` only through adapter-compatible changes
- Create: `tests_web/test_browser_sessions.py`, `tests_web/test_collection_tasks.py`

**Interfaces:**
- `BrowserConnector.start(user_id: UUID) -> BrowserSessionView`
- `BrowserConnector.status(user_id: UUID) -> BrowserSessionView`
- `BrowserConnector.stop(user_id: UUID) -> None`
- `BrowserConnector.collect(user_id: UUID, query: SearchTemplateInput) -> CollectionResult`
- `POST /api/browser-sessions/start`
- `GET /api/browser-sessions`
- `POST /api/browser-sessions/stop`
- `POST /api/collection-tasks -> TaskView`
- `GET /api/tasks/{task_id} -> TaskView`

- [ ] **Step 1: Write tests for independent user Profile paths, start/stop idempotency, task state transitions, manual-pause propagation, and no platform write method.** Use a fake connector and local HTML fixtures.
- [ ] **Step 2: Run focused tests and confirm red.**

  Run: `python -m unittest tests_web.test_browser_sessions tests_web.test_collection_tasks -v`

  Expected: FAIL because the web connector and task services do not exist.
- [ ] **Step 3: Implement the per-user Chromium Profile manager.** Derive the Profile path from a server-owned root and user UUID; do not accept arbitrary paths from requests; use Playwright persistent contexts.
- [ ] **Step 4: Adapt existing BOSS parsing and access guards.** Map successful results into the public `Job` model and map login/CAPTCHA/rate-limit/anti-bot results to `paused` with an explicit reason.
- [ ] **Step 5: Implement database-backed FastAPI background tasks.** Persist `queued`, `running`, `completed`, `paused`, and `failed`; limit retry count; make one active collection task per user and template.
- [ ] **Step 6: Run focused tests and compile checks.** Real BOSS access is not part of automated tests; perform a user-authorized manual smoke test separately.

---

### Task 8: Add Material Templates, Batch Drafts, Review, and Final Files

**Files:**
- Create: `server/services/material_batches.py`, `server/api/material_batches.py`, `server/api/material_drafts.py`
- Modify: `src/application_workflow.py`, `src/application_archive.py`, `tools/render_docx.py`, `tools/convert_docx_to_pdf.py`, `tools/validate_application_bundle.py`
- Create: `tests_web/test_material_batches.py`, `tests_web/test_material_permissions.py`

**Interfaces:**
- `MaterialBatchService.create(user_id: UUID, job_ids: list[str], template_id: UUID) -> MaterialBatch`
- `MaterialBatchService.run_draft(batch_id: UUID) -> None`
- `MaterialBatchService.review(user_id: UUID, draft_id: UUID, decision: Literal["approved", "changes_requested"], notes: str) -> MaterialDraft`
- `MaterialBatchService.finalize(user_id: UUID, draft_id: UUID) -> list[FileObject]`
- `POST /api/material-batches -> MaterialBatchView`
- `GET /api/material-batches/{batch_id} -> MaterialBatchView`
- `PATCH /api/material-drafts/{draft_id}/review -> MaterialDraftView`
- `POST /api/material-drafts/{draft_id}/finalize -> MaterialFilesView`

- [ ] **Step 1: Write tests for multi-job batch creation, one draft per user/job, independent failure, review gating, user isolation, and finalization only after approval.**
- [ ] **Step 2: Run focused tests and confirm red.**

  Run: `python -m unittest tests_web.test_material_batches tests_web.test_material_permissions -v`

  Expected: FAIL because the batch service and routes do not exist.
- [ ] **Step 3: Add default resume and cover-letter templates plus a user-template metadata model.** Validate uploaded templates before associating them with a user.
- [ ] **Step 4: Connect the existing matching, generation, reviewer, DOCX, PDF, and validation helpers through a per-user service.** Pass only one job, one profile version, one template, and one user-approved draft to each material run.
- [ ] **Step 5: Store draft and final objects in MinIO and metadata in the user's rows.** Keep a failed child task from cancelling unrelated batch children.
- [ ] **Step 6: Run focused tests, the existing material suite, and a local WPS/Word PDF acceptance check when available.**

---

### Task 9: Build the React User and Admin Workflows

**Files:**
- Create: `web/src/api/client.ts`, `web/src/auth/`, `web/src/pages/`, `web/src/components/`, `web/src/types/`
- Create: `web/tests/auth.test.tsx`, `web/tests/jobs.test.tsx`, `web/tests/materials.test.tsx`
- Modify: `web/src/main.tsx`, `web/package.json`

**Interfaces:**
- `apiClient.request<T>(path: string, options?: RequestInit) -> Promise<T>`
- `useCurrentUser()`, `useJobs()`, `useTask(taskId)`, `useMaterialBatch(batchId)`
- Pages: `Register`, `Login`, `ProfileReview`, `SearchTemplates`, `BossConnection`, `JobList`, `JobEvaluation`, `MaterialBatchReview`, `Settings`, `Admin`

- [ ] **Step 1: Write frontend tests for invite registration, private job evaluation columns, multi-select batch creation, per-draft review, and admin-only navigation.** Mock API responses, not authorization decisions.
- [ ] **Step 2: Run the focused frontend tests and confirm red.**

  Run from `web/`: `npm test -- --run`

  Expected: FAIL because the React routes and components do not exist.
- [ ] **Step 3: Implement authenticated API client and route guards.** Use same-origin HttpOnly session cookies and show `401/403` states without exposing private response data.
- [ ] **Step 4: Implement onboarding and job pages.** Support document upload, consent, proposal confirmation, template editing, BOSS connection state, job filtering, scoring explanations, and multi-selection.
- [ ] **Step 5: Implement batch progress and per-job draft review.** Disable finalization until the individual draft is approved; allow retry only for the failed draft.
- [ ] **Step 6: Implement the minimal admin pages.** Show invite/account/task metadata only; do not create private-content preview components.
- [ ] **Step 7: Run frontend tests and TypeScript build.**

  Run from `web/`: `npm test -- --run` and `npm run build`

  Expected: PASS with a production build in `web/dist`.

---

### Task 10: Integrate the Local Pilot and Run End-to-End Acceptance

**Files:**
- Create: `tests_web/test_end_to_end_pilot.py`, `tests_web/fixtures/`
- Modify: `docker-compose.yml`, `README.md`, `AGENTS.md`, `.env.example`

- [ ] **Step 1: Add an offline two-user fixture flow.** Create two users, register them with separate invites, upload synthetic documents, confirm different profiles, insert one shared job, create different evaluations, and assert cross-user access is denied.
- [ ] **Step 2: Run the offline end-to-end test and confirm red for any missing integration.**

  Run: `python -m unittest tests_web.test_end_to_end_pilot -v`

  Expected: FAIL until all web services are wired together.
- [ ] **Step 3: Wire Compose health checks and local startup instructions.** Include MinIO bucket initialization, SQLite migration, FastAPI startup, React startup, and Chromium Profile root configuration.
- [ ] **Step 4: Run the complete backend and existing suites.**

  Run: `python -m unittest discover -s tests -p "test_*.py"` and `python -m unittest discover -s tests_web -p "test_*.py"`

  Expected: all tests PASS.
- [ ] **Step 5: Run the local manual acceptance flow.** Use two invitees, complete BOSS login in separate Chromium Profiles, collect an authorized read-only fixture or user-authorized smoke result, select multiple jobs, review drafts, generate DOCX/PDF, and verify each user's MinIO objects and database records are private.
- [ ] **Step 6: Run `git diff --check`, `python -m compileall -q server src crawlers tools`, and the frontend production build.** Record missing local services or WPS/Word PDF prerequisites explicitly.

## Self-Review

- Spec coverage: authentication, invite registration, strict user isolation, shared job cache, user-specific preferences and scoring, MinIO storage, AI consent and key precedence, per-user BOSS Profiles, paused access states, batch drafts, review gating, DOCX/PDF output, React pages, local deployment, and the two-user acceptance flow are covered by Tasks 1-10.
- Placeholder scan: no unresolved placeholder marker or unspecified implementation step is used.
- Interface consistency: `user_id` is explicit in service boundaries; `Job` is public while `UserJobEvaluation` is private; `MaterialBatch` owns child `MaterialDraft` records; task statuses are shared across collection, profile, evaluation, and material work.
- Scope control: the first release is limited to BOSS and local 2-10 user operation. Public deployment, cloud storage, PostgreSQL, Redis/Celery, email recovery, and the local browser Agent are explicit migration work, not hidden MVP dependencies.
- Git control: the plan does not authorize automatic dependency installation, live platform access, commit, push, stash, or cleanup.
