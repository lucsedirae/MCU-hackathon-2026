# Document History and Team Review Implementation

The interview decisions below define the implemented first release. The application uses React, FastAPI, and PostgreSQL in the existing Docker Compose stack.

## Confirmed product decisions

- Support all three document types: curriculum documents, review reports, and run transcripts.
- Each review workspace contains one curriculum, its revisions, associated review reports, and run transcripts.
- Only administrators can create review workspaces. An administrator assigns the owner of each workspace.
- Administrators can transfer workspace ownership but do not automatically receive owner permissions. Uploading proposed revisions, starting review runs, and accepting curriculum proposals remain restricted to the assigned owner.
- The first release supports a small team with individual login accounts. Comments and revisions identify their author. Preserve imported comment author metadata separately from authenticated account identity.
- Team members sign in with app-managed email and password accounts. New passwords require at least 8 characters. An administrator creates users; organization identity-provider integration is not part of the first release.
- For the first release, administrators create accounts and provide temporary passwords. Users must change their temporary password at first sign-in. Email invitations and an email service are not required.
- App-generated curriculum revisions are saved as proposals and must be previewed and explicitly accepted before becoming the current revision.
- Uploaded curriculum revisions follow the same proposal workflow: preview and explicit workspace-owner acceptance are required before they become current.
- In the first release, owners accept or reject curriculum proposals as a whole, or request another revision. Selecting individual changes for acceptance is out of scope.
- Multiple curriculum proposals can be pending simultaneously. Each proposal records its base revision. Accepting one flags other proposals based on an older accepted revision as outdated.
- An outdated proposal can be accepted only after the workspace owner reviews a fresh comparison against the current accepted curriculum and explicitly confirms replacement. This replaces the current content; it does not automatically merge competing proposals. If the current revision changes again before acceptance, require another comparison.
- Rejected proposals remain in history with their content, comments, and reviews intact. The workspace owner can reopen them; outdated-proposal comparison requirements still apply.
- Restoring an older accepted curriculum creates a new proposal from that snapshot. The owner must preview its differences from the current curriculum and explicitly accept it; intervening history is preserved.
- Only the workspace owner can accept proposed curriculum revisions. Other workspace members can review and comment.
- Every team account can access every review workspace; workspace invitations are not required. Acceptance of proposed curriculum revisions remains restricted to the workspace owner.
- Only the workspace owner can upload proposed revisions and start review runs. Other team members can view and comment.
- Curriculum documents can originate from user uploads or app generation. New revisions can likewise come from an uploaded revised file or app-generated revised content.
- Review reports originate from app generation. Users can edit a report externally and upload it as a new revision. Generated reports reference the exact curriculum revision reviewed.
- Review report revisions become current immediately when saved, without a separate approval step. Curriculum revision acceptance remains a separate owner-only action.
- Each review run produces a separate report linked to that run and the exact curriculum revision reviewed. External edits become revisions of that report, rather than combining reports from different runs into one document.
- The workspace owner can start a review run against either the accepted curriculum or a selected pending proposal. The run and report clearly identify the exact revision reviewed and whether it was a proposal at review time.
- Each run has its own transcript. Append output while the run is active, then freeze the transcript when the run finishes or stops. Reruns create separate transcripts; completed transcripts are not editable.
- The first release accepts Word (`.docx`), PDF, Markdown, plain-text, and Moodle (`.mbz`) uploads.
- Preserve each original uploaded file alongside its processed revision and make the original available for download.
- Previews and Word exports use a standardized app layout, preserving document structure such as headings, lists, tables, and images where the source format permits reliable extraction. Exact original fonts, spacing, headers, footers, and pagination are not required. Surface import limitations rather than silently promising full fidelity.
- Revision comparisons show text and structural changes, including added, removed, or moved sections, list items, and table content. Ignore styling changes.
- PDF support in the first release is limited to text-based PDFs. OCR is out of scope; explain when a scanned PDF requires conversion before uploading.
- Import existing comments from uploaded Word documents, including their text attachments and available author/date information. Flag comments whose attachments cannot be mapped.
- Curriculum documents and review reports support both selected-text comments and whole-document comments.
- Comment threads support replies, resolution, and reopening.
- The workspace owner and the thread author can resolve or reopen a comment thread. Imported author metadata alone does not grant account permissions.
- When requesting an app-generated curriculum revision, the owner selects which unresolved comment threads the app should address.
- During acceptance of a generated curriculum revision, offer the owner a choice of which selected comment threads to resolve. Resolve only explicitly chosen threads; leave the others open.
- Carry comments forward to new revisions when their text can be matched. Flag attachments for review when the passage changes or disappears, and preserve the original revision context.
- Word export offers a clean document or a document with unresolved comments represented as native Word comments attached to the relevant passages.

## Implementation structure

### 1. Accounts and workspaces

- Database-backed sessions with hashed passwords, administrator-created accounts, mandatory temporary-password changes, and administrator password resets.
- Administrators create workspaces and assign or transfer their single owner. Administrators receive no implicit owner permissions.
- All signed-in team members can read all workspaces and participate in comments.
- Only administrators configure the shared model connection.

### 2. Documents and revisions

- One curriculum document per workspace; separate report and transcript documents per run.
- Full structured snapshots in PostgreSQL, with content hashes, author attribution, base revision, approval status, and change descriptions.
- Original upload bytes are retained separately. Content-identical uploads reuse the selected base revision while retaining the uploaded original; imports with comments receive their own revision.
- Workspace row locks serialize revision numbering and approval changes. Uploads include the expected current revision to detect stale browser state.
- Original source files, revisions, export snapshots, and discussion history are retained without automatic pruning in this release.

### 3. Proposal workflow and review runs

- Upload or generate multiple pending curriculum proposals.
- Preview text and structural changes; record the user, proposal, and comparison target.
- Acceptance requires a comparison against the still-current curriculum. Accept whole proposals only.
- Rejected proposals can be reopened. Restoring old curriculum content creates another proposal.
- Owners may review accepted revisions or pending proposals. Every run stores its exact source revision and whether it was a proposal at the time.
- Completed, failed, stopped, and interrupted runs produce permanent transcripts. Restarted processes mark unfinished runs interrupted rather than pretending they completed.
- Model calls run in the backend using the existing configured provider. A stop freezes the run and discards late provider results; it cannot guarantee cancellation of provider billing.

### 4. Comments and exports

- General and selected-text comments, including selections inside table cells; replies; author/owner resolution and reopening.
- Preserve original revision, selected passage, author, and date. Carry comments through revision ancestry and prior accepted history.
- Match unchanged block/selection positions first, then unique exact quotations; ambiguous or missing text is visibly unplaced.
- Word uploads preserve available comment metadata. Export comments use native Word annotations; reply discussions are represented as attributed text inside each annotation.
- Clean and commented Word/Markdown exports are available for any saved revision.
- General Word comments attach to a General comments appendix; unmatched comments attach to an Unplaced comments appendix with the original quotation.
- Export cache keys include the revision, format, exporter version, and comment snapshot. Previously generated bytes remain stored when comments later change.

### 5. Import and rendering boundaries

- Accept DOCX, text-based PDF, UTF-8 Markdown, UTF-8 text, and Moodle MBZ course backups, with a 20 MB upload limit and a 200,000-character extracted-text limit.
- Standardize Word layout and preserve reliably extracted headings, lists, tables, and embedded images. Preserve originals for comparison.
- PDF imports extract page text and disclose that tables, images, and reading order may need checking. Pages without extractable text require conversion before upload; OCR is not included.
- Markdown remote images are not fetched. Complex Word structures and unsupported image formats are disclosed as import limitations.
- Generated proposals preserve recognized source-image markers and warn if source images are omitted. Model reviews receive textual content rather than image understanding.

### 6. Validation

- Backend integration tests create and remove a separate PostgreSQL database, apply Alembic migrations, and mock provider calls.
- Cover authentication, permission boundaries, stale acceptance, parallel uploads, restoration, proposal reopening, comment permissions and carry-forward, Word comment round-tripping, cached exports, permanent transcripts, reports, import structures, and failure handling.
- Browser smoke test uses an isolated Compose project: first-admin setup, workspace creation, upload, general and selected-text comments, comparison, acceptance, Word download, reload persistence, and mobile layout.
- Build the React frontend and render a representative exported Word document for visual verification.

### 7. Operating the first release

- Existing PostgreSQL and LLM-settings volumes remain the persistent stores; no new external service is required.
- Bootstrap the first administrator through the local app before sharing access. Existing provider settings are retained.
- Deploy behind HTTPS and set secure cookies before enabling remote team access. The provided Compose configuration remains bound to localhost.
- Run one backend process for this initial background-run implementation. A separate durable worker/queue is a future scaling enhancement.
- See README.md for startup, tests, backup, restore, and known format limitations.

## Completion criteria

A team can upload or generate a curriculum, discuss passages, review proposals, accept a selected revision, retain per-run reports and transcripts, restore history through proposals, and download original files or version-specific Word/Markdown exports. Data survives application restarts.

## Course package import addition

Support standalone SCORM and xAPI (Tin Can/cmi5) ZIP course packages for curriculum review. Extract manifest structure and referenced static HTML/text; retain the original and require preview/acceptance through the existing workflow. Show extraction limitations. Course playback, LRS records, and packages nested in Moodle backups remain outside this addition.
