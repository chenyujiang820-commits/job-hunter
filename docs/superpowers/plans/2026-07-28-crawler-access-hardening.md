# Crawler Access Hardening Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with a focused test cycle after each task.

**Goal:** Make the Zhilian and BOSS read-only crawlers report manual intervention explicitly, repair the coordinator, and declare a reproducible Python environment.

**Architecture:** Keep successful crawler calls returning normalized job lists. Represent login, CAPTCHA, anti-bot, rate-limit, and abnormal-response states with `ManualInterventionRequired`; the coordinator converts that exception into a structured paused result. Keep all access read-only.

**Tech Stack:** Python 3.10+, `curl_cffi`, BeautifulSoup 4, `websocket-client`, `httpx`, Playwright, stdlib `unittest`.

## Global Constraints

- Do not solve CAPTCHA, bypass login, use credential stuffing, or perform platform writes.
- Do not install dependencies during this task; add pinned declarations and report the environment requirement.
- Preserve manual paste intake and the existing `JobSummary` contract.
- Treat platform access failures as explicit paused states, never silent empty success.

### Task 1: Access Guard

**Files:** Create `crawlers/access_guard.py`; Test `tests/test_access_guard.py`.

- [x] Add failing tests for CAPTCHA text, login/rate-limit status, normal HTML, and the exact paused status.
- [x] Implement `ManualInterventionRequired` and response inspection.
- [x] Run the focused tests.

### Task 2: Crawler Integration

**Files:** Modify `crawlers/zhilian.py`, `crawlers/boss_cdp.py`; Test existing crawler tests and new guard cases.

- [x] Add response checks before parsing Zhilian HTML.
- [x] Raise the explicit exception for BOSS API/page access states.
- [x] Preserve successful parsing behavior.
- [x] Run the available BOSS and guard tests.

### Task 3: Coordinator Repair

**Files:** Modify `crawlers/coordinator.py`; Test `tests/test_coordinator.py`.

- [x] Add failing tests for pause status, error propagation, and `total_new`.
- [x] Fix the detail-loop indentation.
- [x] Accumulate `merge_seen_jobs().new_count` and return structured status.
- [x] Run coordinator tests and compile checks.

### Task 4: Reproducible Dependencies

**Files:** Create `requirements.txt`, `requirements-dev.txt`.

- [x] Pin runtime crawler dependencies.
- [x] Pin the test/runtime tooling required by the project.
- [x] Verify declarations are present; installation remains pending explicit authorization.

### Task 5: Full Verification

- [x] Run the focused tests in the available environment.
- [x] Run the complete unittest suite.
- [x] Rerun the complete suite after dependency installation: 112/112 passed.
