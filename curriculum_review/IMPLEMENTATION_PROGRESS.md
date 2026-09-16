# Course builder progress — review milestone

Implemented on `dev`, 2026-09-16. Changes are uncommitted. This is the first staged milestone, not completion of the full implementation plan.

## Initial milestone (historical baseline; specialist update below)

- Any signed-in builder can create and own a review or creation-intake workspace. Existing workspaces retain their legacy workflow.
- Administrators upload, inspect and publish immutable ADDIE guidance versions. New workspaces use the saved instructional-model default and explicitly pin published guidance. No fabricated framework content is installed.
- Builder source uploads and conversation persist. Intake notes work without guidance; model-dependent interviews/reviews are blocked until guidance and sources exist.
- Review uses versioned shared/coordinator instructions and a bounded AI quality reviewer, with validated structured outputs and per-source confidence. A failed quality check does not publish a report.
- AI comments attach to exact source text where verified, with general/unplaced fallback. Only owners resolve builder comments.
- Consequential findings remain proposals until explicit owner verification. Routine edits, declined proposals, transcripts and recoverable versions remain outside consequential project history.
- Report approval is owner-only and bound to the reviewed revision, evidence and state. Peer-review dispositions require a reason. Approving the report does not approve the curriculum.
- Owners can stop tasks; late, stale or malformed outputs cannot apply reports/comments. Legacy generation endpoints cannot bypass builder checks.
- Export includes canonical Word reports, complete recorded conversation, verified history and revision/status manifest.

## Initial requirements placement

| Master prompt requirement | Implemented location | Boundary |
| --- | --- | --- |
| Authority, source discipline, model policy | Shared instructions and API checks | Framework corpus still needed |
| Intake and review synthesis | Coordinator instructions and Builder conversation | Creation supports intake only |
| Separate quality check | Reviewer instructions and bounded second call | AI review is not human peer review |
| Owner-verified state/history | Proposal verification API and separate records | Full dependency graph/supersession workflow remains later |
| Confidence and peer-review disposition | Structured source assessments, report, approval action | Real-model calibration not yet evaluated |
| Preserved export | Existing Word renderer and package assembly | PowerPoint/full curriculum package remains later |
| Framework knowledge | Pinned lexical passage retrieval with source IDs | Semantic retrieval and corpus evaluation remain later |

## Validation

- The initial 39 backend regression tests passed and cover synthetic builder workflows, permissions, missing guidance, state verification, declined changes, stale/stopped/malformed outputs, incomplete confidence coverage, report approval, exports, and existing document behavior.
- Frontend production build passes.
- Isolated browser QA passes admin/member workspace creation, uploads/source reading, saved intake, framework publication/pinning, desktop/mobile layout, and tour navigation/dismissal/role variants.
- Automated checks use synthetic fixtures, isolated databases/settings and mocked providers. No real provider calls or production accounts/data were used for tests.
- Additive database migrations `0003`–`0004` applied to the local development app; existing records and credentials preserved. README and user tour updated.

## Remaining stages after the initial milestone

Receive and curate the peer-authored ADDIE corpus; evaluate retrieval and model quality; add full framework phase/checkpoint enforcement, richer evidence/dependency registers, controlled external research, six-category curriculum production, PowerPoint export, administrative instruction publishing, and same-model guidance updates. Moodle export stays deferred. Current guidance upload accepts one consolidated document per version; current task context rejects oversized collections rather than silently truncating them.

Open the local app and choose **Start course builder** to review the new workflow. Without published guidance, uploads and intake notes are available immediately.

## Chat-first refinement

Builder now uses a single conversation composer with attachments and drag-and-drop. The coordinator routes natural-language requests to intake or substantive review; review still requires the quality check. Workspace details holds sources, pinned guidance and history. Explicit approval cards remain in the conversation. No approval or project-state change is inferred from chat text.

Chat-first validation: all 18 builder tests pass with mocked providers, including natural-language review routing, factual intake before uploads, missing-guidance handling, and report-aware follow-up. Browser QA passes file selection, actual drag/drop, single Send, source reading, framework connection, administrator/member tour variants and mobile layout.

## Agent-led workflow refinement

The Learning Expert introduces the process, requests initial materials, identifies what evidence establishes, and asks the next necessary questions. In review workspaces, sufficient evidence leads to review without requiring another task-selection request. Published guidance is selected automatically once, at creation or when an owner resumes a waiting workspace; existing pinned versions never switch automatically. Missing guidance remains an administrator dependency. Owner verification and approvals remain explicit.

Agent-led validation: all 22 builder tests pass with mocked providers. Browser QA passes automatic guidance connection, attachments, source reading, administrator/member tour navigation and dismissal, and mobile layout. No live model evaluation was performed.

## Retrieval-backed specialist review

Implemented on dev: immutable passage indexing and local BM25 retrieval; administrator-published subject references pinned per run; ISD planning with subject confirmation, full/narrow/quick scopes; SME, assessment, military exercise and technical/accessibility assignments; independent inspection, SME challenge and bounded verification; per-passage coverage and cross-document checks; consolidated reports with preserved specialist findings and evidence locations; anchored source comments; visible chat delegation and on-demand findings. No source text is silently removed to fit a combined request. Material blockers and preliminary/incomplete coverage prevent approval.

Settings now displays the effective versioned agent instructions rather than the obsolete shared prompt editor. No hardcoded lorem ipsum was found in the current source; this rebuild removes the misleading control without changing saved credentials. Shared reference publishing is available alongside framework guidance. Migration 0005 adds evidence, references and task records without resetting existing data.

Prototype limits: local lexical search (no semantic embeddings); serial specialist execution; fixed call/time/conservative token bounds; no code execution, external search, automatic retry or partial-result resumption. Restart recovery marks unfinished work interrupted and retains completed specialist records. Source images/layout are not visually inspected. Formal accessibility certification, full creation and Moodle export remain out of scope. Live model/educator quality evaluation remains outstanding.

Validation: 60 backend regression tests passed with synthetic fixtures and mocked providers, including a complete staged review beyond the former 140,000-character workspace limit. Frontend production build and isolated browser QA passed settings persistence, shared-reference publication, chat uploads, delegation logs, specialist evidence display, coverage and blocked approval, administrator/member tour behavior, keyboard dismissal/navigation, and desktop/mobile layouts. No real provider calls were made.

Owner-authorized prototype reset: cleared four existing course workspaces and dependent documents, conversations, comments, review tasks and source indexes. Accounts, API configuration and shared framework/reference libraries were retained. The local app was restarted successfully.

## Large Moodle backup uploads

Raised the MBZ upload limit to 1 GB (other file types remain 20 MB). Moodle originals are copied with bounded buffers to a persistent upload volume and downloaded as streamed files; they are no longer stored as large database byte arrays. Migration 0006 preserves earlier originals. Parsing keeps separate limits: 4 GB expanded archive, 10,000 entries, 16 MB per XML file, 64 MB selected XML total and 2,000,000 extracted text characters. Code does not load embedded media into agent context. Failed imports and rolled-back database transactions clean up staged originals.

Validation: 68 backend tests passed, including a synthetic backup exceeding the previous upload limit, ZIP and gzip/TAR parsing, source/revision API uploads, original downloads, rollback/close cleanup, archive limits and all existing review tests. Updated tour text passed mocked browser checks for administrator/member variants, keyboard interaction and mobile layout. No real provider calls or user course data were used.

### Moodle text-cap correction

Removed the separate 2,000,000-character MBZ ceiling. Moodle ingestion is bounded by the existing archive/XML safeguards, independently of model request budgets. Verified that a synthetic course exceeding two million characters uploads successfully, retains the original backup, and indexes all course text through its final marker. All 12 targeted Moodle/upload checks passed; the application remains healthy. Other formats retain their extracted-text limits.

## Sequential ISD interpretation and guided clarification

File analysis now has a separate interpretation stage grounded in retrieved, pinned guidance for the configured instructional model. It renders a TLDR, framework implications and priority gaps, then displays the first specific clarification question. Initial excerpt analysis remains preliminary; completed reviews retain the full report and specialist findings. Raw replies, framework citations and the ordered question queue are stored with the task. Subsequent answers receive that queue and conversation context without automatically approving decisions or starting another full review.

Validation: 43 builder tests passed with mocked providers, covering stage ordering, raw-report retention, initial-file analysis, configured-model grounding, invalid framework citations and follow-up context. Frontend build and mocked administrator/member tour checks passed, including keyboard interaction and mobile layout. Live model behavior has not been evaluated in these checks.

### Sidebar progress and consolidated navigation (2026-09-16)
- Added a persistent sidebar with saved system activity, latest task status, scoped passage coverage, and task history. A lightweight authenticated endpoint omits source text and model prompts; it reads existing records without changing verified state.
- Moved workspace selection, section navigation, ownership controls, account/help and administrator settings beneath progress. Conversation workspace details render in the sidebar. Mobile stacks the rail above content with collapsible navigation.
- Updated README and UserTour. Verification: frontend build; isolated progress endpoint test; mocked browser checks for administrator/member, workspace switching, incomplete status, tour keyboard navigation/Escape/focus restoration, and 390px layout; formatted chat regression. No real accounts or provider calls used.
