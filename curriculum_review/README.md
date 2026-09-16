# Curriculum Review

A self-hosted curriculum review application built with React, FastAPI, and PostgreSQL. It supports team accounts, curriculum proposals, immutable content revisions, review reports, run transcripts, comments, and Word/Markdown exports.

## Start

```sh
docker compose up --build -d --wait
```

Open http://localhost:5173. On the first visit, create the administrator account. Then:

1. In **Team**, create accounts with temporary passwords of at least 8 characters. Users must change them at first sign-in.
2. Create a workspace and assign an owner. Each workspace contains one curriculum.
3. As its owner, select the curriculum and upload a DOCX, text-based PDF, Markdown, text, or Moodle `.mbz` backup file, or generate an initial curriculum from instructions.
4. Select **Preview changes**, then **Accept entire proposal**. Uploaded and generated curricula remain proposals until accepted.
5. Team members can select a passage or table-cell text and add comments, reply, and review version history.
6. Owners can run model reviews against accepted content or proposals. Each run gets its own report and permanent transcript.
7. Download any revision as Word or Markdown, with optional unresolved comments, or retrieve an original upload.

API documentation: http://localhost:8000/docs. Health: http://localhost:8000/api/health.

The first administrator setup is available only until an account exists. Complete setup locally before sharing the app. No email service is needed; administrators can issue new temporary passwords from Team. Password changes and resets revoke existing sessions.

## Permissions

| Action | Team member | Workspace owner | Administrator |
|---|---|---|---|
| View all workspaces, history, originals, and exports | Yes | Yes | Yes |
| Comment and reply | Yes | Yes | Yes |
| Resolve/reopen a thread | Own threads | Any workspace thread | Own threads unless also owner |
| Upload revisions, generate proposals, start/stop runs | No | Yes | Only if assigned owner |
| Accept/reject/reopen/restore curriculum proposals | No | Yes | Only if assigned owner |
| Create workspaces and assign/transfer owners | No | No | Yes |
| Manage accounts and model settings | No | No | Yes |

## Revision behavior

- Curriculum uploads and generation create pending proposals. Multiple proposals may coexist.
- Acceptance replaces the entire current curriculum; it does not merge competing changes.
- An outdated proposal requires a fresh comparison against the current curriculum. A concurrent acceptance invalidates earlier approval comparisons.
- Rejected proposals retain content and comments and may be reopened by the owner.
- Restoring old curriculum content creates a proposal. Restoring a report creates a new current report revision.
- Reports originate from review runs. Owners can upload external edits as report revisions, which become current immediately.
- Transcripts append while a run is active and freeze when completed, failed, stopped, or interrupted. Reruns create new transcripts.
- Revision content is not edited in place through the API. Approval status and comment state are tracked separately.
- Identical normalized uploads reuse their base revision while preserving the original file. Imports containing comments create a revision so imported feedback is retained.

## Comments and exports

Comments retain their original revision context. The app carries them through revision ancestry, first matching an unchanged block and range, then a unique exact quotation. Ambiguous or missing passages are labeled **Attachment needs review** rather than attached to an arbitrary occurrence.

Owners choose which unresolved discussions a generated curriculum should address. At acceptance, they can explicitly resolve selected threads. Other selected threads remain open.

Word exports use native comments on supported text ranges. Replies are included as attributed discussion text inside the annotation, not modern Word reply objects. General comments and comments without a matched passage appear in labeled appendices. Clean exports omit feedback. Markdown exports put feedback in a Comments section.

Generated exports are stored as exact bytes in Postgres. The cache includes the document revision, export format, exporter version, and comment snapshot. Adding or resolving comments creates a different export snapshot without replacing earlier stored files. Use **Previously generated exports** to download an exact older snapshot.

## Import limits

- Up to 20 MB per file and 200,000 extracted text characters.
- DOCX: standardized headings, paragraphs, lists, tables, and supported embedded raster images. Check complex fields, nested tables, tracked changes, and unsupported images against the retained original.
- PDF: up to 300 pages, extracted as page text. Layout, tables, and images are not reconstructed. Pages without extractable text are rejected with OCR guidance.
- Moodle `.mbz`: Moodle 2+ full course backups in ZIP or gzip/TAR format. Imports the course title/summary, ordered sections and activities, page and book text, lesson pages, assignment instructions, URLs, and available question-bank text. Only activity names/descriptions are available for some activity types. Embedded resource files, media, SCORM/H5P content, activity rules/settings, and learner data are not extracted into the review text. The original backup is retained in full, including any learner data it contains, and is downloadable by all team members. Archives are limited to 100 MB expanded size, 10,000 entries, and 16 MB per imported XML file.
- Markdown/plain text: UTF-8. Markdown headings, lists, and tables are normalized; external images are not fetched.
- Styling, fonts, headers/footers, and exact pagination are not preserved.
- Model review uses textual context. Image references can be retained in generated proposals, but the current provider integration does not perform image analysis.

## Model connection

An administrator saves an OpenAI API key, then chooses a model from the dropdown in **Settings**. The API address is fixed to OpenAI. Previously saved credentials and model IDs for other providers are ignored; enter the new OpenAI key and model. Existing system instructions, guardrails, rubric, evidence rules, and examples remain supported. **Test connection** and review/generation runs send requests to OpenAI and may incur OpenAI charges.

The API key remains encrypted in the persistent `llm_settings` volume. It is not returned to the browser. Back up this volume to retain the connection and encryption key.

Runs currently use background tasks in a single backend process. A restart freezes unfinished runs as interrupted. Stopping a run discards a late response; it does not guarantee that the provider cancels processing or billing. There are no real provider calls in the automated tests.

## Development and verification

Frontend and backend source changes reload automatically. Rebuild after dependency changes.

```sh
docker compose exec frontend npm run build
docker compose exec backend python -m unittest discover -s tests -v
docker compose exec backend alembic current
```

Document integration tests create a uniquely named `cr_test_...` PostgreSQL database, apply migrations, and remove it afterward. They require the configured database account to have `CREATEDB`; the local Compose account does. Application tables and settings are not modified by these tests. LLM tests use temporary settings and mocked providers.

`qa/browser-smoke.cjs` exercises an isolated, empty QA app. It requires Playwright (or `PLAYWRIGHT_MODULE` pointing to playwright-core), a Chromium installation (`CHROME_PATH` when needed), and an app at `QA_URL` (default http://localhost:15173). It deliberately creates test accounts and sample content; use a separate Compose project with separate database volumes. Screenshots and a sample export are saved under `/private/tmp` by default on macOS.

## Persistence and backup

The `postgres_data` volume stores accounts, sessions, workspace ownership, revisions, original files, runs, comments, audit events, and exports. Content and export snapshots are retained without automatic pruning. The `llm_settings` volume stores provider configuration and the encryption key.

Create a database backup:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > curriculum-review.dump
```

Also back up the `llm_settings` volume using your Docker volume backup procedure. Restore the dump into a new database with `pg_restore`, retaining the corresponding settings backup. Test restores before relying on them.

`docker compose down` preserves volumes. **`docker compose down -v` permanently deletes the project's database and model settings.**

## Deployment settings

The supplied Compose file binds web ports to localhost and keeps Postgres internal. For team hosting, provide an HTTPS reverse proxy and set `COOKIE_SECURE=true` in the backend environment. Sessions are HTTP-only, SameSite Strict cookies with a 12-hour lifetime. Passwords use salted scrypt hashes. Browser cross-site mutation requests are rejected; the app expects same-origin API access.

The first release has shared team-wide visibility and one owner per workspace. It does not provide public registration, per-workspace invitations, email reset links, multiple backend workers, or a distributed job queue.

## Layout

```text
backend/app/auth.py         Accounts, sessions, administrator provisioning
backend/app/models.py       Persistent data model
backend/app/documents.py    Workspaces, proposals, comments, exports, runs
backend/app/content.py      Import, comparison, anchoring, Word/Markdown export
backend/app/moodle.py       Moodle course-backup text extraction
backend/app/llm.py          Existing model settings and provider integration
backend/migrations/        Alembic schema history
backend/tests/             Isolated integration tests and mocked-provider tests
frontend/src/ReviewApp.jsx  Team and document workflows
frontend/src/Settings.jsx   Model connection and review instructions
qa/browser-smoke.cjs        Browser workflow validation
IMPLEMENTATION_PLAN.md     Consolidated product decisions and implementation
```

### SCORM and xAPI course packages

Upload a `.zip` containing a root `imsmanifest.xml` (SCORM 1.2/2004), `tincan.xml` (Tin Can), or `cmi5.xml` manifest. Imports course titles, descriptions, and referenced HTML/plain-text pages into the existing preview, acceptance, commenting, and export workflow. SCORM uses the default organization and item order. Limits: 20 MB upload, 100 MB expanded, 10,000 entries, 16 MB per imported file.

This is static text extraction, not a course player or LRS connection. JavaScript-generated content, media, learner activity records, external pages, and proprietary authoring data are not analyzed. Review import warnings for missing or incomplete content. For packages embedded in Moodle backups, upload the original course ZIP separately.

## Workspace navigation

Use **Curriculum**, **Proposals**, **Reports**, and **Activity** to move between workspace tasks. Document actions are grouped under **Review**, **Revise**, **Download**, and **History**. Comments can be collapsed or filtered by status. Administration contains team accounts and OpenAI settings; the user menu contains account and sign-out controls. See [UX_PLAN.md](UX_PLAN.md) for the complete feature map.
