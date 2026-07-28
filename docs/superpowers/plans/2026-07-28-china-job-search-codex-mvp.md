# China Job Search Codex MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a Codex-native, manually triggered MVP that searches public Zhilianshaopin listings for junior technical product-manager roles in Zhejiang, ranks them against the confirmed candidate profile, and generates user-approved DOCX and PDF application materials locally.

**Architecture:** Keep the reference project's portable Bun portal-CLI contract, local JSON/CSV/Markdown state, candidate-profile workflow, two-stage search/rank flow, and factual-review gates. Add a small shared normalization/state layer, one `ZhilianAdapter`, and a Python document renderer; translate Claude Code-specific orchestration into Codex project guidance and a portable local skill.

**Tech Stack:** Codex workflow instructions, Bun + TypeScript for the portal CLI, Python 3.10+ for local state/document helpers, `python-docx` for DOCX output, LibreOffice `soffice --headless` for PDF conversion, JSON/CSV/Markdown for local state, fixture tests plus bounded live smoke tests.

## Global Constraints

- The first release targets only public, read-only Zhilianshaopin search/detail access; it must stop on login, CAPTCHA, SMS verification, or anti-bot pages.
- The first release is manually triggered; no scheduler, daemon, browser automation, upload, submission, chat, reply, or platform write operation is allowed.
- The first release targets junior product-manager roles in Zhejiang, prioritizing Lishui, then Hangzhou/Jinhua, then other Zhejiang cities.
- The hard exclusions are labor dispatch and outsourcing; salary has no hard floor and is shown as a ranking reference only.
- Candidate sources are PDF, DOCX, Markdown, and plain text under `documents/`; profile changes require explicit user confirmation.
- Every selected job produces both a tailored resume and cover letter; unselected jobs produce no application materials.
- Final materials require factual validation, reviewer assessment, user approval, DOCX generation, and PDF generation.
- Candidate data, generated materials, tracker state, and email contents remain local; future external sync is behind an adapter and is not enabled in this MVP.
- Do not add or upgrade dependencies without user authorization; confirm package name, source, version, and license before installation.
- Do not commit, push, stash, or create a safety commit automatically; commits remain a user decision.

## Reference Context

The implementation uses the reference project at `ai-job-search-master/` as read-only source material. Its main reusable seams are:

- `ai-job-search-master/.agents/skills/*/`: portable Bun CLI and portal-skill contract.
- `ai-job-search-master/.claude/commands/`: behavior to translate into Codex workflow guidance, not files to execute directly.
- `ai-job-search-master/.claude/skills/job-application-assistant/`: candidate profile, evaluation, template, and interview concepts.
- `ai-job-search-master/.claude/skills/job-scraper/`: two-stage search, deduplication, health checks, and local state behavior.
- `ai-job-search-master/tools/` and `tests/`: validation and fixture-test patterns.

The project root is the new implementation target. The ignored `ai-job-search-master/` directory must not be modified.

### Task 1: Establish the Codex-Native Project Contract

**Files:**
- Create: `AGENTS.md`
- Create: `.agents/skills/domestic-job-search/SKILL.md`
- Create: `.agents/skills/domestic-job-search/references/candidate-profile.md`
- Create: `.agents/skills/domestic-job-search/references/job-evaluation.md`
- Create: `.agents/skills/domestic-job-search/references/search-queries.md`
- Create: `documents/README.md`
- Modify: `.gitignore`
- Test: `tests/test_project_contract.py`

**Interfaces:**
- `AGENTS.md` tells Codex to load the domestic-job-search skill for manual search, rank, and apply requests and defines the local-only/write-gate rules.
- `SKILL.md` exposes the workflow phases `scrape`, `rank`, `apply`, and `outcome` as Codex-readable procedures; it does not depend on Claude Code slash-command execution.
- `references/job-evaluation.md` keeps the reference scoring dimensions and adds the confirmed candidate constraints.
- `documents/README.md` defines the supported source extensions and the directory layout.

- [ ] **Step 1: Write contract tests**

  Test that the skill and reference files exist, the skill names the four workflow phases, the documents guide names PDF/DOCX/Markdown/plain text, and the ignore rules cover candidate files, generated application files, tracker state, and runtime caches.

- [ ] **Step 2: Run the contract tests**

  Run: `python -m unittest tests.test_project_contract -v`

  Expected: FAIL because the Codex contract files do not exist yet.

- [ ] **Step 3: Write the Codex contract and local-data rules**

  Define the manual workflow in this order:

  ```text
  scrape -> inspect/cache new jobs -> rank -> user selects job -> apply -> local archive
  ```

  Define the candidate constraints exactly as approved: bachelor degree, former graduate, communications-engineering background, party-member status enabled by default, Lishui/Hangzhou-Jinhua/other-Zhejiang city tiers, dispatch/outsourcing exclusion, no salary floor, on-site work allowed, moderate travel allowed, long-term on-site assignment flagged.

  Add `.gitignore` rules that keep `documents/**`, `job_search_tracker.csv`, `job_scraper/**`, generated resume/cover-letter outputs, and runtime secrets local while preserving tracked README and template files.

- [ ] **Step 4: Run the contract tests**

  Run: `python -m unittest tests.test_project_contract -v`

  Expected: PASS.

### Task 2: Add Candidate-Document Inventory and Confirmed Profile State

**Files:**
- Create: `tools/inventory_candidate_documents.py`
- Create: `tools/profile_state.py`
- Create: `profiles/candidate-profile.md`
- Create: `profiles/job-preferences.md`
- Modify: `documents/README.md`
- Test: `tests/test_candidate_documents.py`

**Interfaces:**
- `inventory_candidate_documents(root: Path) -> list[DocumentRecord]` returns sorted records with `path`, `extension`, `size_bytes`, and `relative_folder` for `.pdf`, `.docx`, `.md`, and `.txt` files.
- `load_confirmed_profile(path: Path) -> CandidateProfile` reads only confirmed profile facts.
- `write_profile_proposal(path: Path, proposal: ProfileProposal) -> Path` writes a reviewable proposal outside the confirmed profile.
- `apply_confirmed_profile_changes(path: Path, changes: list[ProfileChange]) -> None` is the only helper allowed to update the confirmed profile.

- [ ] **Step 1: Write inventory and write-gate tests**

  Cover supported and unsupported extensions, deterministic ordering, empty folders, proposal generation without confirmed-profile mutation, and applying only explicitly confirmed changes.

- [ ] **Step 2: Run the focused tests**

  Run: `python -m unittest tests.test_candidate_documents -v`

  Expected: FAIL because the inventory and profile-state helpers do not exist.

- [ ] **Step 3: Implement the inventory and profile-state helpers**

  Keep source documents immutable. Store proposal files under ignored runtime state, include the source path for each proposed fact, and reject profile writes when a proposal lacks an explicit confirmation marker.

- [ ] **Step 4: Populate the confirmed preference baseline**

  Store the approved profile and preference rules in `profiles/` without embedding them in Python constants. The Codex skill reads these files at runtime.

- [ ] **Step 5: Run the focused tests**

  Run: `python -m unittest tests.test_candidate_documents -v`

  Expected: PASS.

### Task 3: Verify Zhilianshaopin Access Before Implementing a Parser

**Files:**
- Create: `docs/portal-research/zhaopin.md`
- Create: `docs/portal-research/zhaopin-fixtures/README.md`
- Test: `tests/test_zhaopin_research_record.py`

**Interfaces:**
- `zhaopin.md` records the verified search URL/API, detail URL, query/location/recency parameters, field anchors, response examples, robots.txt result, access requirements, rate limits, and service-term notes.
- A captured fixture must include one search response and one detail response with sensitive account data removed.

- [ ] **Step 1: Write the research-record test**

  Require the research record to state whether search and detail are public, list the exact fields needed by the normalized contract, and state a go/no-go result. Reject a record that relies on a logged-in session or CAPTCHA bypass.

- [ ] **Step 2: Run the research-record test**

  Run: `python -m unittest tests.test_zhaopin_research_record -v`

  Expected: FAIL until the current portal behavior is recorded.

- [ ] **Step 3: Perform a bounded manual investigation**

  Check the current public search and detail paths, robots.txt, terms/access requirements, one realistic query for junior technical product roles in Zhejiang, and one detail page. Capture only the minimum fixture data needed for parser tests.

- [ ] **Step 4: Run the research-record test**

  Run: `python -m unittest tests.test_zhaopin_research_record -v`

  Expected: PASS only when the access decision and parsing anchors are complete. If the result is no-go, stop the portal implementation and revise the MVP to use user-supplied posting URLs or an approved public source; do not bypass the restriction.

### Task 4: Implement the Zhilianshaopin Read-Only CLI

**Files:**
- Create: `.agents/skills/zhaopin-search/SKILL.md`
- Create: `.agents/skills/zhaopin-search/url-reference.md`
- Create: `.agents/skills/zhaopin-search/cli/package.json`
- Create: `.agents/skills/zhaopin-search/cli/tsconfig.json`
- Create: `.agents/skills/zhaopin-search/cli/README.md`
- Create: `.agents/skills/zhaopin-search/cli/src/cli.ts`
- Create: `.agents/skills/zhaopin-search/cli/src/helpers.ts`
- Create: `.agents/skills/zhaopin-search/cli/src/commands/search.ts`
- Create: `.agents/skills/zhaopin-search/cli/src/commands/detail.ts`
- Create: `.agents/skills/zhaopin-search/cli/tests/helpers.ts`
- Create: `.agents/skills/zhaopin-search/cli/tests/parsing.test.ts`
- Create: `.agents/skills/zhaopin-search/cli/tests/cli-contract.test.ts`
- Create: `.agents/skills/zhaopin-search/cli/tests/request-timeout.test.ts`

**Interfaces:**
- CLI: `bun run src/cli.ts search --query <text> --location <text> --jobage <days> --page <n> --limit <n> --format json|table|plain`.
- CLI: `bun run src/cli.ts detail <id|url> --format json|plain`.
- JSON search output: `{ "meta": { "count": number, "page": number }, "results": JobSummary[] }`.
- `JobSummary` fields: `id`, `title`, `company`, `location`, `salary`, `experience`, `education`, `date`, `url`, and `source`.
- Errors go to stderr as JSON with `error` and `code`; stdout remains machine-readable output.

- [ ] **Step 1: Copy the contract test harness from the reference CLI pattern**

  Reuse the `runCLI` and JSON parsing test shape from `ai-job-search-master/.agents/skills/jobindex-search/cli/tests/helpers.ts`, adapting only the path and command name.

- [ ] **Step 2: Write parser fixture tests**

  Add tests for one captured search response, one captured detail response, missing salary, Chinese text/entity decoding, malformed cards, and detail-not-found behavior.

- [ ] **Step 3: Run the Bun tests**

  Run: `bun test --cwd .agents/skills/zhaopin-search/cli`

  Expected: FAIL because the CLI and parsers are not implemented.

- [ ] **Step 4: Implement the minimal read-only CLI**

  Follow the reference portal contract: `fetch` with a browser-like user agent, a 15-second abort signal, bounded retry for 429/5xx, `null` for unavailable optional fields, per-result parsing isolation, and no authenticated request headers.

- [ ] **Step 5: Run typecheck and fixture tests**

  Run: `bun run --cwd .agents/skills/zhaopin-search/cli typecheck`

  Expected: PASS with no TypeScript errors.

  Run: `bun test --cwd .agents/skills/zhaopin-search/cli`

  Expected: PASS with all fixture and contract tests passing.

- [ ] **Step 6: Run one bounded live smoke test**

  Run the documented junior technical-product query with `--limit 3 --format json`, then run `detail` on one returned ID. Confirm populated title/company/URL fields and readable description. Do not use the live request in CI and stop immediately on login/CAPTCHA/rate-limit evidence.

### Task 5: Add Shared Job State and Deterministic Hard Filters

**Files:**
- Create: `src/job_state.py`
- Create: `src/job_schema.py`
- Create: `src/ranking_rules.py`
- Create: `tests/test_job_state.py`
- Create: `tests/test_ranking_rules.py`
- Modify: `.agents/skills/domestic-job-search/SKILL.md`

**Interfaces:**
- `canonical_job_key(job: JobSummary) -> str` prefers `source + id`, then normalized URL, then normalized company/title.
- `merge_seen_jobs(path: Path, jobs: list[JobSummary], today: str) -> MergeReport` updates additive state and returns new/duplicate/updated counts.
- `apply_hard_filters(job: JobSummary, profile: CandidateProfile) -> FilterResult` returns `passed`, `reasons`, and `flags`.
- `location_tier(location: str) -> Literal["lishui", "hangzhou_jinhua", "other_zhejiang", "outside"]`.

- [ ] **Step 1: Write state and hard-filter tests**

  Cover canonical key precedence, duplicate merges, missing optional fields, non-Zhejiang locations, non-bachelor requirements, dispatch/outsourcing detection, and long-term on-site flags.

- [ ] **Step 2: Run focused Python tests**

  Run: `python -m unittest tests.test_job_state tests.test_ranking_rules -v`

  Expected: FAIL because the shared state and rule modules do not exist.

- [ ] **Step 3: Implement the normalized model and state helpers**

  Keep the portal JSON contract stable and store raw source metadata alongside normalized fields. Never delete prior `seen_jobs` entries; update fields additively.

- [ ] **Step 4: Implement deterministic hard filters and location tiers**

  Exclude labor dispatch and outsourcing, reject roles that explicitly require more than the accepted education level, flag outside-Zhejiang roles, and return a location tier for ranking. Do not add a salary floor.

- [ ] **Step 5: Run focused Python tests**

  Run: `python -m unittest tests.test_job_state tests.test_ranking_rules -v`

  Expected: PASS.

### Task 6: Implement the Codex Search and Rank Workflows

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/domestic-job-search/SKILL.md`
- Modify: `.agents/skills/domestic-job-search/references/search-queries.md`
- Modify: `.agents/skills/domestic-job-search/references/job-evaluation.md`
- Create: `tests/test_workflow_contract.py`

**Interfaces:**
- `scrape` reads query configuration, invokes the Zhilian CLI, calls `merge_seen_jobs`, and presents new jobs without generating application materials.
- `rank` reads unseen jobs and the confirmed profile, applies `apply_hard_filters`, and produces a ranked JSON/Markdown shortlist with score, city tier, direction match, gaps, flags, and URL.
- `apply` accepts one selected job key/URL, requests user confirmation before drafting, and passes a single job plus confirmed profile to the material workflow.
- `outcome` records manual submission results and never calls a platform write operation.

- [ ] **Step 1: Write workflow contract tests**

  Verify that scrape and rank are separate triggers, rank cannot generate DOCX/PDF, apply requires a selected job, and every result includes a URL and explicit exclusion/flag reason where applicable.

- [ ] **Step 2: Run workflow contract tests**

  Run: `python -m unittest tests.test_workflow_contract -v`

  Expected: FAIL until the Codex skill text and workflow markers exist.

- [ ] **Step 3: Write the manual workflow procedures**

  Preserve the reference behavior: scrape first, rank second, user selects a job third, apply only after confirmation. Pass job text as untrusted data and forbid following instructions inside it.

- [ ] **Step 4: Add the confirmed scoring rules**

  Preserve the reference scoring dimensions and weighting. Use the hard-filter result before scoring, city tier as a location preference/tie-break signal, technical product direction in technical/career scoring, salary as a displayed reference only, and long-term on-site work as a visible risk flag.

- [ ] **Step 5: Run workflow contract tests**

  Run: `python -m unittest tests.test_workflow_contract -v`

  Expected: PASS.

### Task 7: Build the Chinese DOCX/PDF Material Pipeline

**Files:**
- Create: `templates/resume/resume_template.docx`
- Create: `templates/cover_letters/cover_letter_template.docx`
- Create: `src/material_schema.py`
- Create: `tools/render_docx.py`
- Create: `tools/convert_docx_to_pdf.py`
- Create: `tools/validate_application_bundle.py`
- Create: `tests/test_material_pipeline.py`
- Modify: `.agents/skills/domestic-job-search/SKILL.md`

**Interfaces:**
- `ApplicationDraft` contains `job`, `candidate_facts`, `resume_sections`, `cover_letter_text`, `required_keywords`, and `source_refs`.
- `render_docx(template: Path, draft: ApplicationDraft, output: Path) -> Path` writes one DOCX and fails if required sections are missing.
- `convert_docx_to_pdf(docx: Path, output_dir: Path, soffice: str = "soffice") -> Path` invokes `soffice --headless --convert-to pdf` and verifies the expected PDF exists.
- `validate_application_bundle(docx: Path, pdf: Path, required_terms: list[str]) -> ValidationReport` checks file readability, required terms, PDF page/text extraction, and no missing output.

- [ ] **Step 1: Write material and tool-preflight tests**

  Cover missing template fields, required resume/cover-letter sections, Chinese text preservation, missing `soffice`, failed conversion, missing PDF, and successful DOCX/PDF bundle validation.

- [ ] **Step 2: Run focused material tests**

  Run: `python -m unittest tests.test_material_pipeline -v`

  Expected: FAIL because the renderer and templates do not exist.

- [ ] **Step 3: Add the approved DOCX templates**

  Use separate resume and cover-letter templates with stable headings, Chinese-capable fonts, predictable spacing, and placeholders represented by named content controls or clearly marked template paragraphs.

- [ ] **Step 4: Implement DOCX rendering**

  Use `python-docx` to replace template placeholders, preserve style definitions, write the selected job/company/role in metadata, and keep candidate source references in a local manifest rather than visible material text.

- [ ] **Step 5: Implement PDF conversion and validation**

  Check `soffice` before conversion, use a temporary output directory, verify the PDF exists, and use `pdftotext` or an equivalent local extractor to confirm Chinese text and required terms. Never report success when conversion or validation fails.

- [ ] **Step 6: Run material tests**

  Run: `python -m unittest tests.test_material_pipeline -v`

  Expected: PASS when the DOCX path is available; conversion-specific tests must explicitly report a skipped prerequisite when `soffice` is absent rather than silently passing.

### Task 8: Integrate User Confirmation, Reviewer, and Local Archive

**Files:**
- Create: `src/application_archive.py`
- Create: `tests/test_application_archive.py`
- Modify: `.agents/skills/domestic-job-search/SKILL.md`
- Modify: `documents/README.md`
- Modify: `.gitignore`

**Interfaces:**
- `archive_application(job: JobSummary, bundle: ApplicationBundle, root: Path) -> ArchiveRecord` copies the final DOCX/PDF, saves the source posting and draft manifest, and appends a tracker row without overwriting an existing submitted archive.
- `require_user_confirmation(action: str, payload_summary: str) -> bool` is a workflow gate; no archive or profile write occurs when it returns false.
- `ArchiveRecord` contains the job key, company, role, source URL, generated file paths, creation date, and confirmation marker.

- [ ] **Step 1: Write archive and gate tests**

  Cover confirmation rejection, repeated archive idempotency, existing submitted-material preservation, local-only file paths, and tracker row creation.

- [ ] **Step 2: Run focused archive tests**

  Run: `python -m unittest tests.test_application_archive -v`

  Expected: FAIL because archive and gate helpers do not exist.

- [ ] **Step 3: Implement append-safe local archive behavior**

  Store application records under `documents/applications/<company>_<role>/`, preserve the first submitted bundle, append notes instead of rewriting history, and never call an external destination.

- [ ] **Step 4: Connect the workflow gates**

  Require confirmation before profile writes, material generation, final bundle acceptance, and archive writes. Keep Reviewer feedback separate from candidate source facts and require final user approval after revision.

- [ ] **Step 5: Run focused archive tests**

  Run: `python -m unittest tests.test_application_archive -v`

  Expected: PASS.

### Task 9: Run MVP Verification and Document the Local Setup

**Files:**
- Create: `README.md`
- Create: `.github/workflows/ci.yml`
- Create: `tests/test_mvp_contract.py`
- Modify: `AGENTS.md`

**Interfaces:**
- README documents manual Codex triggers, prerequisites, local-only data rules, the public-read-only platform boundary, and the current MVP limitations.
- CI runs offline Python tests and Bun fixture/typecheck tests; it does not call Zhilianshaopin or any live mailbox.

- [ ] **Step 1: Write the final MVP contract tests**

  Assert that the project exposes only the first-phase capabilities, names QQ sync and other portals as later phases, and contains no workflow instruction for platform write operations.

- [ ] **Step 2: Run the complete offline suite**

  Run: `python -m unittest discover -s tests -v`

  Expected: PASS for all Python tests.

  Run: `bun test --cwd .agents/skills/zhaopin-search/cli`

  Expected: PASS for all fixture tests.

  Run: `bun run --cwd .agents/skills/zhaopin-search/cli typecheck`

  Expected: PASS with no TypeScript errors.

- [ ] **Step 3: Run the manual end-to-end acceptance flow**

  Place representative PDF, DOCX, Markdown, and text candidate files under `documents/`; run manual scrape; run rank; select one Zhejiang junior technical-product job; approve draft generation; complete factual validation and Reviewer review; approve final materials; verify DOCX, PDF, tracker, and archive outputs.

- [ ] **Step 4: Record environment limitations**

  On the current Windows environment, Python is available but LibreOffice/`soffice`, Typst, and Pandoc were not detected during planning. The first implementation run must install or otherwise provide the approved DOCX/PDF dependencies before PDF acceptance can pass.

## Out of Scope for This Plan

- QQ IMAP/POP3 implementation; it receives a separate second-phase plan after the MVP is stable.
- 163 and enterprise-mail adapters.
- BOSS, Liepin, and 51job adapters.
- Notion or other external synchronization implementation.
- Web UI, scheduler, daemon, browser extension, platform login, platform upload, platform submission, chat, reply, and CAPTCHA handling.

## Plan Self-Review

- Spec coverage: candidate ingestion, Codex workflow, Zhilianshaopin access gate, read-only CLI, normalization, hard filters, two-stage ranking, DOCX/PDF generation, user confirmations, local archive, tests, and MVP acceptance each have dedicated tasks.
- Placeholder scan: no `TODO`, `TBD`, `待定`, or unspecified implementation placeholder is used; the Zhilianshaopin access decision is an explicit go/no-go gate with a defined stop/fallback behavior.
- Type consistency: `JobSummary`, `CandidateProfile`, `ApplicationDraft`, `ApplicationBundle`, `FilterResult`, `ArchiveRecord`, and all referenced function names are defined at their first use and reused consistently.
- Dependency risk: `python-docx` and LibreOffice are named as prerequisites and require authorization before installation; no dependency installation is included in this plan.
