# Cadence

A self-hosted curriculum review application built with React, FastAPI, and PostgreSQL. It supports team accounts, curriculum proposals, immutable content revisions, review reports, run transcripts, comments, and Word/Markdown exports.

## Start

```sh
docker compose up --build -d --wait
```

Open http://localhost:5173. On the first visit, create the administrator account. Then:

1. In **Administration → Team accounts**, create accounts with temporary passwords of at least 8 characters. Users must change them at first sign-in.
2. In **Administration → OpenAI settings**, save the connection. New workspaces currently use ADDIE. Inspect the active ISD instructions; publish your framework guidance and any shared subject references in the libraries below.
3. Choose **Start course builder**, name a review workspace, and attach your course materials in the conversation. Supported source imports include DOCX, text-based PDF, Markdown, text, Moodle `.mbz`, and supported SCORM/xAPI `.zip` packages.
4. Answer the ISD's focused intake questions. It confirms subject areas and delegates reviews to specialists automatically. Full review is the default; ask for a narrow review or quick screening in chat when appropriate.
5. Read the consolidated report, specialist findings, evidence citations and coverage. Review anchored comments and explicitly confirm or decline proposed consequential changes. Material issues and incomplete coverage prevent approval.
6. Download the report package, transcript, specialist records and owner-verified history from **Workspace details**. Owners can stop a running review; stopped or interrupted reviews remain visibly incomplete.

Older document editing screens remain available, but no backward-compatibility commitment applies to this prototype. The course builder is the primary workflow.


API documentation: http://localhost:8000/docs. Health: http://localhost:8000/api/health.

The first administrator setup is available only until an account exists. Complete setup locally before sharing the app. No email service is needed; administrators can issue new temporary passwords from Team. Password changes and resets revoke existing sessions.

## Permissions

| Action | Team member | Workspace owner | Administrator |
|---|---|---|---|
| View all workspaces, history, originals, and exports | Yes | Yes | Yes |
| Comment and reply | Yes | Yes | Yes |
| Resolve/reopen a legacy thread | Own threads | Any workspace thread | Own threads unless also owner |
| Resolve/reopen builder review comments | No | Yes | Only if assigned owner |
| Upload revisions, generate proposals, start/stop runs | No | Yes | Only if assigned owner |
| Accept/reject/reopen/restore curriculum proposals | No | Yes | Only if assigned owner |
| Create a builder workspace owned by yourself | Yes | Yes | Yes |
| Create legacy workspaces; assign/transfer owners | No | No | Yes |
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

- Moodle backups: up to 1 GB per file, with no separate extracted-character cap; archive/XML limits below bound ingestion. Other files: up to 20 MB and 200,000 extracted text characters.
- DOCX: standardized headings, paragraphs, lists, tables, and supported embedded raster images. Check complex fields, nested tables, tracked changes, and unsupported images against the retained original.
- PDF: up to 300 pages, extracted as page text. Layout, tables, and images are not reconstructed. Pages without extractable text are rejected with OCR guidance.
- Moodle `.mbz`: Moodle 2+ full course backups in ZIP or gzip/TAR format. Imports the course title/summary, ordered sections and activities, page and book text, lesson pages, assignment instructions, URLs, and available question-bank text. Only activity names/descriptions are available for some activity types. Embedded resource files, media, SCORM/H5P content, activity rules/settings, and learner data are not extracted into the review text. The original backup is retained in full, including any learner data it contains, and is downloadable by all team members. Moodle archives are limited to 4 GB expanded size, 10,000 entries, 16 MB per imported XML file, and 64 MB of imported XML in total.
- Markdown/plain text: UTF-8. Markdown headings, lists, and tables are normalized; external images are not fetched.
- Styling, fonts, headers/footers, and exact pagination are not preserved.
- Model review uses textual context. Image references can be retained in generated proposals, but the current provider integration does not perform image analysis.

## Model connection

An administrator saves an OpenAI API key, then chooses a model from the dropdown in **Settings**. The API address is fixed to OpenAI. Previously saved credentials and model IDs for other providers are ignored; enter the new OpenAI key and model. Builder requests use the active versioned ISD and specialist instructions shown in Settings. **Test connection** and review/generation runs send requests to OpenAI and may incur OpenAI charges.

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

## User tour

Select **User tour** in the signed-in app header. Use **Next**, **Back**, or **Jump to a topic**. **Close**, **Finish tour**, or Escape returns you to your work. The tour does not modify data or make AI requests, and can be reopened at any time. Administrators see additional configuration and team-management steps.

1. **Choose a workspace:** use the sidebar. Everyone can view/comment; owners control uploads, AI runs, and proposal decisions.
2. **Navigate:** Curriculum for the current document, Proposals for pending/rejected changes, Reports for findings, Activity for jobs and transcripts.
3. **Add content:** upload in an empty curriculum or choose Revise. Read import limitations before accepting converted content.
4. **Discuss:** select paragraph or table-cell text, or add a general comment. Expand replies; filter Open, Resolved, Needs placement, or All. Show passage locates the text; original context opens the source version. On mobile, use Back to document to return to reading.
5. **Review:** owners choose Review, enter instructions, and start a job. OpenAI must be configured; requests may incur API charges.
6. **Revise:** upload or generate a proposal. Select open curriculum comments to include their feedback in generation.
7. **Decide:** preview the document, review changes against the current curriculum, then accept the entire proposal or reject it. Outdated proposals require careful comparison; changed current versions require a fresh preview. Rejected proposals can be reopened.
8. **Follow results:** Reports support comments and revisions; uploaded report revisions become current immediately. Activity includes source/results, stop controls, and permanent read-only transcripts. Stopping may not cancel provider processing or billing.
9. **Retrieve history:** History provides versions, comparisons, restoration, and exact saved exports. Curriculum restoration creates a proposal; report restoration creates a new current revision.
10. **Download:** choose Word, Markdown, or originals, with optional unresolved comments.
11. **Administration:** configure OpenAI and shared instructions; create/reset team accounts and assign workspace owners. Administrative access alone does not confer owner permissions.
12. **Account:** use your user menu to change your password or sign out.

### Where are the system prompt fields?

Administrators: **Administration → OpenAI settings → System prompt & instructional model**. This section is expanded by default and displays the effective planner, coordinator, specialist and quality-review instructions with version hashes. Instructions are read-only here and maintained under `backend/app/instructions/`; the obsolete shared prompt editor has been removed. The Model selector appears only in the framework upload form; new workspaces currently use ADDIE. Non-administrators cannot access administration settings.

### Documentation maintenance

Before every commit and push to `dev`, update this README and the in-app tour to match the change. See the repository-root `AGENTS.md` for the standing workflow. Changes without a user-facing effect still require a documented review of both sources.

- 2026-09-15: Added the role-aware user tour and made system prompt fields visible by default. Reviewed tour and README against the current workspace workflows.

- 2026-09-16: Renamed the application to Cadence across the interface, browser title, API documentation, and user tour. Existing project paths, Docker volumes, and export identifiers remain compatible.

### Instructional model configuration

In **Administration → OpenAI settings → System prompt & instructional model**, **Instructional Model** is saved as the default for new builder workspaces. ADDIE is currently the only option. Existing legacy workflows retain their behavior; builder workspaces retain their creation-time model and explicitly pinned guidance version.

- 2026-09-16: Added the ADDIE instructional model placeholder; updated the user tour and README to explain its inactive status.

- 2026-09-16: Simplified shared prompts to System prompt only. Removed Guardrails, Review rubric, Evidence rules, and Examples from settings and request assembly, including previously saved values. Per-run instructions and the ADDIE placeholder remain. Tour reviewed and updated.


## Course builder — review milestone

Any signed-in user can **Start course builder**, choose review or creation intake, and become its owner. Existing workspaces remain in the legacy workflow. Team-wide visibility is unchanged.

1. An administrator opens **Administration → OpenAI settings → Instructional framework library**, selects **Model** (currently ADDIE), uploads a curated guidance document with a unique version, inspects it, and publishes it. The guidance title is generated from the selected model. Versions are immutable. No sample or improvised ADDIE guidance is installed. Consolidate the framework materials into one supported document per version for this milestone.
2. The latest available published guidance for the configured model is pinned automatically when a workspace is created. A waiting workspace connects when its owner next opens it or sends a message after publication. Once pinned, newer publications do not change it. The model and pinned version cannot be changed through this release. Without guidance, source uploads and saved intake notes work, but AI interviews/reviews are blocked.
3. Attach or drop source files in the conversation composer, type a message, and choose **Send**. The Learning Expert leads intake, inspects sources, asks focused gap questions, and proceeds with the agreed review when evidence is sufficient. Without framework guidance, messages are saved and the conversation explains the setup needed. All existing import formats/limits apply. Open source documents through **Workspace details** to read and comment on passages.
4. In a review workspace, provide the requested materials and answers; the Learning Expert determines the next review step. The ISD confirms inferred subject areas, delegates bounded tasks to SMEs, an assessment specialist, a military exercise specialist and a technical/accessibility analyst as appropriate, and synthesizes their findings. Full review includes SME and technical coverage; relevant assessment/exercise tasks and cross-document alignment checks supplement it. Specialists inspect evidence independently, then an SME challenge round questions findings and assumptions. Consequential disagreements receive one targeted verification pass and remain for owner decision. Delegations appear in chat. No agent provides independent human peer review.
5. Review proposed consequential changes and their rationale/impact. An inline **Confirm or decline this change** card requires owner verification or a decline reason. Routine edits, discussions and declined proposals do not enter verified project history. Full conversation and recoverable revisions remain separately available.
6. Review the report and its per-source confidence explanations. **Review and approve** beside the report opens the explicit approval form and records owner approval for that exact report revision and a peer-review disposition. It does not approve the assessed curriculum or resolve source comments. Changed evidence/state requires a fresh review. Material findings or incomplete coverage block approval; declining a recommendation does not clear a material blocker. Quick screening is not approvable as a completed review. Narrow review approval applies only to its recorded scope.
7. Under **Workspace details**, download the review package: Word reports, a conversation transcript, consequential verified history, a revision/status manifest, and specialist task/findings records. The report text is preserved; the manifest carries the current approval status. Individual source/report downloads and Word comments remain available in the document view.

### Current boundaries

- Creation workspaces support source organization and interviews only. Six-category course production, PowerPoint export, external research discovery/approval, same-model guidance upgrades, and model-specific phase gates are subsequent milestones. Moodle export remains deferred.
- Originals and revisions are stored; normalized text is indexed into passages with revision/block IDs, offsets and PDF pages where extraction preserves them. Local BM25 lexical search retrieves from pinned framework guidance, published shared references and workspace sources. This is retrieval-backed review, not an evaluated semantic embedding index. Administrators upload and publish references through **Shared reference library**; the newest published version of each titled reference is pinned per review run.
- The former 140,000-character combined-context rejection is removed. Full/narrow reviews inspect scoped indexed text in batches, with cross-document checks, coverage records and complete specialist findings retained in the report appendix. Quick review samples text and explicitly reports its limits. Source images and visual layout are not analyzed; code/markup inspection is static and practical accessibility checks do not certify compliance. Moodle uploads allow 1 GB with archive/XML safeguards instead of an extracted-character cap; other uploads allow 20 MB and 200,000 extracted characters. Text-based PDFs remain limited to 300 pages.
- One parent task runs per workspace; specialists execute serially with no recursive spawning, code execution or external search. A run allows 120 provider calls, 30 minutes, up to three additional retrieval rounds per assignment, and conservative UTF-8-byte token upper bounds of 48,000 per request and 2,000,000 per run (including a 4,096-token output reserve per call). These are processing safeguards, not monetary budgets or a claim about the provider model's exact context capacity. Oversized work remains explicitly incomplete. Prototype limits live in `backend/app/orchestration.py`.
- Stop discards late results. Source/owner/verified-state changes invalidate the run. Completed specialist findings survive failures; Task activity shows details and evidence. Restart marks unfinished work interrupted; send a new message to retry against current evidence. Automatic retries, task resumption from partial results and a distributed worker queue are not implemented.
- Framework guidance, shared references and instructions are versioned separately. Settings shows the instructions actually used by the builder; a saved obsolete prompt cannot override them. No compatibility adapter is required for this prototype.
- Automated builder tests use synthetic in-memory SQLite fixtures and mocked providers. Existing document integration tests use disposable PostgreSQL databases. Live model quality has not been evaluated; no automated test makes real provider calls.

Documentation maintenance: 2026-09-16 — Added the staged builder review workflow, framework publication/pinning, per-document confidence, owner verification and export boundaries. Updated the user tour to distinguish Builder from legacy workflows and explain active model configuration.

Documentation maintenance: 2026-09-16 — Simplified Builder to conversation, attachments/drag-and-drop, and one Send action. The agent routes intake versus review; explicit owner confirmations remain inline. Files, guidance and history moved into Workspace details. Updated the tour accordingly.

Documentation maintenance: 2026-09-16 — Replaced Guidance title with a validated Model dropdown in framework uploads. New guidance is named from the selected model; existing versions remain unchanged. Reviewed the user tour; its framework-library instructions remain accurate.

Documentation maintenance: 2026-09-16 — Learning Expert now leads intake and review rather than asking the builder to direct the workflow. Published guidance connects automatically once, and manual connection controls were removed. Updated the tour and tested owner-only setup and version stability.

Documentation maintenance: 2026-09-16 — Added retrieval-backed specialist review, coverage and challenge rounds, published shared references, read-only active instructions, evidence inspection and explicit resource/recovery limits. Updated the tour for these controls; settings persistence and role/keyboard/mobile checks are part of validation.

### Specialist browser QA

Use a separate disposable Compose project on frontend port 15174, with synthetic accounts and no provider credentials. Run `qa/builder-smoke.cjs` first. Seed the mocked review by piping `qa/seed-specialist.py` to that QA backend's Python process with `QA_FIXTURES_ONLY=1`; the seed refuses non-synthetic account collections. Then run `qa/specialist-smoke.cjs`. Never run these fixtures against the development user's accounts or database.

Documentation maintenance: 2026-09-16 — Removed the duplicate ADDIE selector from System instructions. The framework upload retains its Model selector; connection saves leave the stored instructional-model default unchanged. Updated tour guidance.

### Large Moodle backups

MBZ uploads are copied in 1 MB buffers and parsed from disk. Original MBZ files live in the persistent `original_uploads` Docker volume; the database stores their references. Back up both the database and this volume together. Original downloads stream from disk. Failed imports or rolled-back database changes remove their staged files. Existing database-backed originals remain downloadable. Embedded media stays in the original archive and is not analyzed by the agent. Archive and extracted-text limits are separate from model review budgets; uploading a large backup does not guarantee that a full review fits one run.

Documentation maintenance: 2026-09-16 — Raised Moodle backup uploads to 1 GB, added disk-backed original storage and streaming downloads, and updated archive/text safeguards. Updated the upload hint and user tour; other file types retain the 20 MB limit.

Documentation maintenance: 2026-09-16 — Removed the separate Moodle extracted-text ceiling. The 1 GB upload, 4 GB expanded archive, 64 MB selected XML, 16 MB individual XML and 10,000-entry safeguards remain. Review request budgets remain separate from ingestion. Reviewed the tour: its upload limits remain accurate, so no user-facing tour wording changed.

Documentation maintenance: 2026-09-16 — Agent chat responses now render Markdown headings, emphasis, lists, tables, links and code blocks. Tables/code scroll within the message on small screens. Raw HTML is not executed and Markdown images display their labels without remote image requests. Saved transcripts retain the original Markdown. Reviewed the tour; its actions and navigation are unchanged.

### Guided review responses

After initial file analysis, or after synthesis and quality checking for a full review, a separate ISD interpretation step reads the raw response using retrieved guidance from the workspace’s configured instructional model and pinned version. Initial analysis remains explicitly preliminary. Chat uses two short paragraphs: what was checked and the most useful finding, then a next step or one necessary question. Framework reasoning, gaps, citations and question rationales remain in task records rather than being appended to chat. Answer in chat to continue the interview; answers do not automatically approve changes or launch another full review. The detailed review and specialist findings remain available, and the raw reply and ordered question queue are retained in task records. New evidence may require reassessment. This step uses one additional model call, with up to three bounded retrieval rounds when needed. Review and creation-intake replies share conversational rules: plain language, no report headings, usually 2–3 sentences and at most 50 words. Requested detail or context for consequential decisions may use up to 250 words. Before display, paragraph count, word count, headings/lists and question marks are checked. A reply that fails gets one bounded rewrite call; if it still fails, the task reports an error rather than truncating the message. These checks enforce structure, not factual accuracy or every aspect of tone; source honesty, jargon avoidance and preservation of important limitations are also instruction requirements. Reports and specialist evidence are not shortened. Full course production remains unavailable.

Documentation maintenance: 2026-09-16 — Added sequential configured-model interpretation, TLDR-first presentation and guided clarification questions after file review. Updated the tour to explain the conversation flow.

### Sidebar progress and navigation

The sidebar records saved analysis activity above navigation, workspace selection, and account/administrator settings. Progress refreshes automatically and survives reopening a workspace. Task status and scoped passage coverage are activity indicators, not curriculum approval or confirmed project state. Workspace details (files, confirmed changes, pinned guidance and export) appears in the sidebar while Conversation is open. On small screens the sidebar stacks above the conversation; collapse Navigation and settings to save space.

Maintenance log — 2026-09-16: reviewed and updated the user tour and README for sidebar progress, consolidated navigation/settings, and mobile behavior.

Documentation maintenance: 2026-09-16 — Replaced report-style chat openings with conversational review and creation-intake replies. Reviewed and updated the user tour; retained detailed analysis, explicit approvals and existing production limits. Added bounded presentation checks and mocked conversation tests.
