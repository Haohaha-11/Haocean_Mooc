# Haojiang Development Plan

## Current Coverage

- Core assignment flow is available: teacher creates assignments, student submits archives, teacher grades, student fetches feedback.
- Email-code login and role tokens are available for student and teacher clients.
- Peer review and final score calculation already exist in Module B:
  - `POST /v1/assignments/peer-review/config`
  - `POST /v1/peer-reviews`
  - `POST /v1/assignments/{assignment_id}/calculate-final-scores`
  - `GET /v1/assignments/{assignment_id}/final-scores`
- Course archive creation, listing, and download already exist in Module B:
  - `POST /v1/archives/course`
  - `GET /v1/archives`
  - `GET /v1/archives/download/{archive_name}`

## New Teacher-Requested Work

1. Automatic plagiarism check
   - Run automatically when a submission is accepted.
   - Compare against submissions from the same assignment and submissions from the last three years.
   - Store the best match and similarity rate.
   - Add teacher-facing report APIs.

2. Grade analytics
   - Provide per-assignment score statistics: count, average, min, max, median, grade distribution.
   - Provide each student's historical assignment scores.

3. Peer/scored presentation assignments
   - Keep the existing peer-review model.
   - Use final score calculation to combine teacher score, peer average, and peer accuracy bonus.
   - Later UI work should expose peer-review configuration and peer scoring from A/C clients.

4. Course archive
   - Existing Module B archive APIs are usable.
   - Later UI work should expose archive creation and download from the teacher client.

## Execution Order

1. Implement backend plagiarism persistence, automatic calculation, and report endpoints.
2. Implement backend grade analytics endpoints.
3. Add focused tests for plagiarism and grade analytics.
4. Update API documentation after endpoint behavior stabilizes.
5. Add teacher/client UI commands for these endpoints after backend coverage is verified.

## First Implementation Batch

- Module B:
  - `plagiarism_reports` table.
  - `plagiarism_rate`, `matched_submission_id`, `matched_student_id`, `scope`, `checked_at`.
  - Automatic report update during `POST /v1/submissions`.
  - `GET /v1/assignments/{assignment_id}/plagiarism`.
  - `GET /v1/submissions/{submission_id}/plagiarism`.
  - `GET /v1/assignments/{assignment_id}/score-stats`.
  - `GET /v1/students/{student_id}/score-history`.

## Validation

- Unit tests should use temporary SQLite databases and temporary submission archives.
- Existing auth and grading tests must continue passing.
- New tests should not touch the live `data/db/engine.db`.

## Executed In This Batch

- Added Module B plagiarism persistence and automatic calculation on submission acceptance.
- Added Module B plagiarism report APIs:
  - `GET /v1/assignments/{assignment_id}/plagiarism`
  - `GET /v1/submissions/{submission_id}/plagiarism`
- Added Module B grade analytics APIs:
  - `GET /v1/assignments/{assignment_id}/score-stats`
  - `GET /v1/students/{student_id}/score-history`
- Added tests:
  - `module_b_server/tests/test_plagiarism_and_stats.py`

## Verified Commands

```bash
cd /Hao/gongchuang/module_b_server
PYTHONPATH=. .venv/bin/python tests/test_plagiarism_and_stats.py
PYTHONPATH=. .venv/bin/python tests/test_auth_flow.py
PYTHONPATH=. .venv/bin/python tests/test_grade_pending_guard.py
```

## Productization Batch

### Objective

Move from repository-local development commands to installable Linux terminal tools:

- Student command: `haocean`
- Teacher command: `haocean-teacher`
- Student local state: `~/.haocean/`
- Teacher local state: `~/.haocean-teacher/`
- Class communication model: teacher creates class and join code; student joins class; class assignments are scoped by enrollment.

### Implemented

- Module B:
  - Added `courses`, `classes`, and `class_enrollments`.
  - Added teacher class APIs:
    - `POST /v1/classes`
    - `GET /v1/classes`
  - Added student class APIs:
    - `POST /v1/classes/join`
    - `GET /v1/classes/my`
  - Added `assignments.class_id`.
  - `GET /v1/assignments/open` now filters class-scoped assignments by student enrollment when auth is enabled.
  - `POST /v1/submissions` rejects class-scoped submissions from students not enrolled in the class.
  - Added teacher download API:
    - `GET /v1/submissions/{submission_id}/download`

- Module A:
  - Added `pyproject.toml` console script: `haocean`.
  - Default public server: `https://student.haoceanlab.cn`.
  - Added `~/.haocean/config.json` support.
  - Added commands:
    - `haocean setup`
    - `haocean login`
    - `haocean join`
    - `haocean classes`
    - `haocean list`
    - `haocean submit`
    - `haocean feedback`
    - `haocean watch`

- Module C:
  - Added `pyproject.toml` console script: `haocean-teacher`.
  - Default public server: `https://teacher.haoceanlab.cn`.
  - Added `~/.haocean-teacher/config.json` support.
  - Added commands:
    - `haocean-teacher setup`
    - `haocean-teacher login`
    - `haocean-teacher classes create/list`
    - `haocean-teacher assignment create`
    - `haocean-teacher plagiarism`
    - `haocean-teacher stats`
    - `haocean-teacher history`
    - `haocean-teacher final-scores`
    - `haocean-teacher archive create/list/download`
    - `haocean-teacher download`

### Verified Commands

```bash
cd /Hao/gongchuang/module_b_server
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests

cd /Hao/gongchuang/module_a_client
PYTHONPATH=. python3 -m unittest discover -s tests

cd /Hao/gongchuang/module_c_controller
.venv/bin/python -m pytest -q
```
