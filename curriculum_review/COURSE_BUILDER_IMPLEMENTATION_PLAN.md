# Course builder implementation plan — draft for review

Status: Retrieval-backed, ISD-led specialist review is implemented on dev with synthetic automated validation; live model and educator evaluation remains outstanding. Full curriculum creation remains a later milestone; see IMPLEMENTATION_PROGRESS.md for completed work, validation, and remaining stages. The master prompt remains the requirements specification. No Moodle .mbz export in this implementation scope.

## Prototype development policy

Backward compatibility is not required during this development cycle. Replace obsolete prompts, interfaces, endpoints and schemas directly where that simplifies the prototype; do not maintain parallel legacy workflows or compatibility adapters. Data migration is optional, not a release requirement. Identify any destructive reset and obtain owner direction before deleting existing documents, settings or credentials. This does not relax evidence traceability, version integrity or owner-approval rules within the new workflow.

## Agreed product behavior

- Any authenticated course builder can create a creation or review workspace and becomes its owner. The owner alone approves checkpoints and documents. The LLM is the primary collaborator; independent peer review is optional, with recorded reasons for declining recommendations.
- Conversation is the primary interface: one Send action, inline attachments/drag-and-drop, and an instructional designer that leads intake, identifies evidence gaps, and advances authorized work without asking the builder to select each activity. Reports and explicit owner confirmations appear in the conversation; files, guidance and history live in secondary workspace details. Chat intake interviews the builder about requirements and gaps. Essential missing evidence blocks substantive affected work, with a tailored submission list; factual intake may continue.
- Creation produces lesson plans, course book, PowerPoint decks, assignments/rubrics, assessments with separate answers/scoring, and syllabus. Confirm .docx/.pptx defaults during intake. Add a package summary/quality report, complete available conversation transcript, and document history.
- Review produces a strengths-and-gaps report and passage comments for owner resolution. It does not require constructing all six categories.
- Each workspace retains its instructional model. The newest available published guidance for that model is pinned automatically at creation, or when an owner resumes a workspace that was waiting for guidance. Framework guidance is versioned and pinned. Same-model documentation updates require explicit review, dependency analysis, and approval; the model itself cannot change.
- Restricted research can be discovered automatically, but curriculum inclusion requires explicit approval of sources and uses. Allowed sources: official doctrine, military education institutions, professional military journals, and published peer-reviewed civilian research. Preserve citations and links.
- Confidence is High/Moderate/Low; readiness is Draft/Needs review/Human-approved. Report these per document in the package summary or review report. Material gaps block approval regardless of comment dismissal or peer-review decline.
- Gate model phases and, for creation, outline, lesson template, and first sample lesson. Produce implementation guidance/evaluation plans without claiming actual delivery or outcome evidence.
- Document activity does not itself change established project state. Ignore insubstantial differences; assess potential instructional impacts and obtain owner verification before recording consequential changes in project state or durable project history. Keep routine edits and review conversation outside that history, while retaining separate recoverable versions and complete transcripts.

## Existing foundation and gaps

Inspected `frontend/src/Settings.jsx`, `backend/app/models.py`, relevant application references, and README on 2026-09-16. This is an initial architectural inventory, not a full implementation audit.

Existing foundation: accounts and workspace ownership; immutable document revisions; passage comments and resolution; proposal acceptance; run transcripts; Word/Markdown export with stored snapshots. Backend data models already separate documents from revisions, but workflows assume one main curriculum document.

Historical gaps at the initial inventory (some now addressed; see IMPLEMENTATION_PROGRESS.md): Instructional Model is a UI placeholder, neither persisted nor supplied to requests. Workspace creation is administrator-only. The requested framework retrieval, persistent builder conversation, six-category artifact workflow, confidence semantics, and gate enforcement require application support; prompt text alone is insufficient.

## Agent architecture

Use one primary Learning Expert as the builder's consistent conversational partner. It interviews, applies the configured framework, coordinates bounded specialist tasks, reconciles findings, and requests owner approvals. Specialists return results to the coordinator rather than taking over the conversation. This follows the [agents-as-tools orchestration pattern](https://developers.openai.com/api/docs/guides/agents/orchestration).

| Role | Bounded responsibility | Next milestone |
| --- | --- | --- |
| Primary ISD / Learning Expert | Interview, infer and confirm subject areas, scope, delegation, evidence synthesis, owner decisions | Required coordinator |
| Subject-matter expert (SME) | Verify subject accuracy and integrity; challenge other SMEs and ISD assumptions with evidence | Multiple subject-specific assignments allowed |
| Assessment specialist | Check objectives, instruction, assessments, rubrics, scoring and alignment | Available for relevant review tasks |
| Military exercise specialist | Review wargames, classroom and field exercises | Available for relevant review tasks |
| Technical and accessibility analyst | Static code/markup inspection, practical accessibility and formatting consistency | Available for relevant review tasks |

The ISD may delegate without builder approval within the established review scope and application resource limits. Agents cannot recursively spawn agents. All four specialist roles are in scope; activate them incrementally as their controls pass validation. The existing quality reviewer is an implementation foundation, not a substitute for these roles.

Specialists first inspect evidence independently, without other agents' conclusions. A second round challenges relevant findings and ISD assumptions, followed by bounded targeted verification where necessary. Unresolved consequential disagreements go to the builder for decision. Evidence, not agent consensus, establishes support. Role labels do not establish expertise.

Exercise criteria initially cover learning-objective alignment, scenario realism, participant roles, resources/timing, facilitation, assessment, after-action review and safety considerations. Technical inspection does not execute uploaded code. Accessibility checks identify practical issues and explicitly do not certify formal standards compliance.

### Instruction placement

- **Shared core policy:** Owner authority, evidence discipline, research restrictions, model/version rules, and delegation boundaries. Supply applicable safeguards explicitly to every agent; do not rely on retrieval to recover mandatory policy.
- **Coordinator instructions:** Interviewing, workflow state, delegation criteria, synthesis, and handoff to the owner.
- **Task-specific instructions:** Specialist responsibilities, artifact requirements, checklists, and output contracts. Load the relevant version explicitly for each task.
- **Framework knowledge base:** Retrieve supporting guidance from the pinned model/version. Keep it separate from course sources and unapproved research.
- **Application controls:** Enforce permissions, approvals, material blockers, immutable history, and content-preserving exports in code. Export assembly is a software operation, not another creative agent role.

Maintain a coverage map from the master requirements specification to these instruction modules and application checks. Shortening the coordinator prompt must not discard requirements or duplicate conflicting policy across roles.

### Delegation contract and controls

Each task receives a task ID, role/instruction versions, workspace/mode, bounded objective, approved course objectives and decisions, relevant source passages with IDs, pinned framework guidance, exact input document revisions, allowed tools, expected output, and resource limits. Specialists may request further evidence through controlled retrieval; they must report missing context instead of guessing.

Return structured proposed artifacts or revision references, evidence-linked findings, coverage, limitations, suggested confidence with rationale, blockers, and questions for the coordinator. Preserve full artifact content in storage rather than relying on a summary passed between agents. Attribute proposals and findings to their producing run.

Only the coordinator presents consolidated questions and recommendations to the builder. All agents remain unable to approve documents, resolve owner comments, or overwrite accepted content. Specialist tool access is scoped to the assignment and workspace. Keep unapproved external research separate from approved evidence across agent boundaries.

The coordinator reconciles disagreements against sources and records unresolved conflicts; it does not average confidence labels or use majority agreement as proof. A separate AI reviewer is still not independent human peer review. Never raise confidence merely because multiple agents agree.

Validate results against current input revisions before integration. Reject or reassess stale results after owner edits or upstream changes. Use bounded retries, cancellation, time/cost/concurrency limits, and idempotent task recording so failures do not create duplicate artifacts or comments. Failed required reviews remain visibly incomplete; do not silently treat fallback output as reviewed.

Record delegation, inputs, output references, failures, and coordinator dispositions in run history. Preserve user-visible transcripts separately from structured agent activity, without storing or exposing private model reasoning.

## Phase 0 — finalize instructions and activation contract

1. Retain `SYSTEM_PROMPT_DRAFT.md` as the master requirements specification. Derive shared policy, a concise coordinator prompt, task instructions, and quality-reviewer instructions; review their requirement coverage with the owner. This plan update does not itself rewrite those prompts.
2. Replace the obsolete single-prompt configuration with versioned shared policy, coordinator and specialist instructions, activating them with their supporting workflow. Rebuild administrative controls around the new architecture; no legacy prompt path is required. Do not incidentally change API credentials or the selected language model.
3. Explicitly report the activation consequence: the new prompt blocks model-dependent work until curated guidance and runtime model context are connected. Do not add an interim ADDIE definition.
4. Record effective shared-policy, coordinator, specialist, and task-instruction versions on each run. Define runtime fields for workspace mode, immutable instructional model, guidance version, current phase, artifact state, and tool capabilities. Do not instruct the coordinator to invoke unavailable specialists; expose actual capability state.

Acceptance: Effective instructions are versioned and recoverable; unsupported capabilities are not represented as operational. Activate the new workflow only with its guidance and enforcement capabilities. Legacy workspace compatibility is not required.

## Phase 1 — curated instructional-model knowledge base

1. Receive the peer-authored ADDIE definitions, instructions, and guidelines. Give administrators a curation/publishing workflow separate from builder course uploads.
2. Store source originals, titles, authority, dates, versions, content hashes, readable sections, and stable source locations. Preserve superseded guidance.
3. Establish reviewed model definitions with phase/activity structure and explicit entry/exit criteria. Keep the representation extensible to other models without embedding ADDIE sequencing in the universal prompt.
4. Build retrieval with filtering by model and pinned guidance version, preserving passage citations. Separate framework retrieval from course-source retrieval and external-research candidates.
5. Handle incomplete retrieval, unreadable files, and missing guidance explicitly. Do not treat empty retrieval as permission to improvise.
6. Evaluate retrieval on curated representative questions and conflicts before activation. Use local fixtures and mocked provider responses for automated tests; any real-provider evaluation requires a separately authorized manual process.

Acceptance: Responses retrieve the correct pinned guidance with stable citations; cross-model/version leakage is prevented; missing required guidance blocks dependent operations. This phase precedes substantive course generation.

## Phase 2 — workspace and artifact data model

1. Permit authenticated builders to create workspaces and assign themselves as owner. Preserve explicit authorization checks for approval and content mutations. Do not widen workspace visibility as an incidental change.
2. Add workspace mode, immutable model identifier, pinned framework version, and phase/checkpoint state. Choose a direct schema update or an explicit prototype reset; migration of old workspaces is optional. Do not invent past framework versions or approvals.
3. Support multiple curriculum artifacts, types, audiences, and linked revisions, replacing single-curriculum assumptions without compatibility adapters.
4. Add durable evidence/requirement/decision/issue registers, objective and concept mappings, dependency links, approval records, exceptions, and research dispositions.
5. Store confidence assessments with rationale, evidence basis, assessor, and revision; readiness/approval separately; peer-review requests and declines separately from material blockers.
6. Store parent/child task relationships, role and instruction versions, input revision references, tool scopes, output artifacts/findings, usage, status, and integration disposition for delegated work.

Acceptance: Records created under the new workflow remain accessible; ownership controls hold; model changes are rejected; approvals attach to specific revisions; answer materials have explicit audience metadata.

## Phase 3 — persistent chat intake and source organization

1. Build a persistent workspace conversation with multi-file uploads, ingestion status, retry/error handling, and an organized source library. Publish supported file types based on actual parsers.
2. Reuse original-upload preservation and extraction where suitable. Retain file/section/page references and distinguish evidence uploads from generated deliverables.
3. Support grouped intake questions, recorded answers, evidence sufficiency checks, and suggested submissions for blockers. Confirm modality, audience, scope, and formats.
4. Reconstruct working context from durable state and retrieved evidence rather than depending on full conversation memory. Capture user-visible conversation and recorded actions without exposing secrets or hidden reasoning.

Acceptance: Resume after reload/interruption; identify unreadable and uninspected sources; do not ask again for recorded answers; missing evidence blocks only dependent work.

## Phase 4 — workflow tools and enforcement

1. Implement model-guided orchestration and structured artifact operations: create drafts, record evidence, propose decisions, add anchored comments, request approval, and identify blockers.
2. Enforce owner-only transitions in the backend, not just the prompt. Gate phases plus outline/template/sample lesson for creation; use review-specific checkpoints for review mode.
3. Stage potentially consequential differences for impact analysis and owner verification. Only verified changes update established project state and consequential history or trigger downstream state changes. Keep proposed findings, routine edits, and review conversation separate. Exact-revision approval checks still prevent an unapproved revision from claiming approval; this does not itself revise established instructional decisions.
4. Make comment resolution an owner action in these workflows. Apply the new owner-only policy consistently; legacy collaborator behavior need not be retained.
5. Add restricted research discovery and an approval queue for specific sources/uses. Verify source eligibility and citations; store pending research apart from approved curriculum evidence.
6. Implement the coordinator's bounded specialist interface, extending the existing quality reviewer to the agreed specialist roles. Validate structured outputs, enforce tool scopes and resource limits, reject stale results, and support cancellation/recovery without duplicate mutations. Keep recursive delegation disabled.
7. Stage reviewer findings as review material; promote consequential changes into established registers and project history only after owner verification. Require coordinator analysis of substantive disagreements and owner action on material blockers; specialist recommendations never constitute approval or verified project state.

Acceptance: The model cannot self-approve, resolve owner decisions, silently incorporate unapproved research, bypass material blockers, or use peer-review decline as evidence of quality. Permission and state-transition rules remain effective against malformed model outputs.

## Phase 5 — document creation and review experience

1. Provide an artifact navigator with clear draft/current versions, pending owner actions, source links, and comments. Keep implementation terminology out of builder-facing flows.
2. Support the agreed lesson template and sample-lesson approval, then sequential complete lesson generation and coordinated updates across all six artifact types.
3. Build the review report and passage-comment workflow with exact revision anchors and fallback general/unplaced comments. Preserve original documents; revisions require owner authorization.
4. Generate package summary/review-report confidence tables, readiness, evidence limitations, peer-review recommendations/dispositions, and unresolved issues.
5. Provide complete conversation and document-history records alongside the report, including approvals and consequential changes.

Acceptance: Creation and review have distinct completion rules; long lessons survive interrupted generation without silent shortening; comments attach to correct text; all document claims and status labels are traceable.

## Phase 6 — verified document exports

1. Extend existing Word export to structured lessons, syllabus, assignments, assessments, course book, and reports; add PowerPoint generation with speaker notes.
2. Assemble from canonical selected revisions with version manifests. Separate learner assessments from answer keys. Preserve draft versus approved status in accompanying reports.
3. Verify content completeness, document structure, links, tables, and slide notes. Render representative fixtures for layout inspection; test long documents and diverse lesson structures.
4. Package the six deliverable categories plus summary, transcripts, and history. Reuse exact stored export snapshots for reproducibility.
5. Defer Moodle .mbz packaging. Keep objectives, activities, assessments, and audience metadata structured so a later exporter can map them without rewriting approved text.

Acceptance: Export does not regenerate content; selected revision content is preserved; files open correctly; notes and answers are neither omitted nor placed in the wrong learner artifact.

## Validation and rollout

Use synthetic sources, local fixtures, mocked LLM/retrieval responses, and nonproduction accounts. Automated tests must never use production data or real provider calls.

Cover owner/member/admin permissions; framework version pinning; missing guidance; retrieval citations; intake resumption; source approval/rejection; model-output failures; creation and review gates; blockers; peer-review decline; anchored comments; revision invalidation; complete exports; and transcript/history retention. Validate server enforcement as well as UI behavior.

Add delegation tests for missing context, unauthorized tools, research approval leakage, stale inputs, contradictory findings, malformed outputs, timeouts, cancellation, retries, resource limits, and attempted recursive spawning. Verify that agent agreement cannot clear blockers or grant human approval.

Verify that routine edits and review discussion do not change established project state or enter consequential history; potential instructional changes remain pending until owner verification. Confirm that separate version recovery, transcripts, and exact-revision approval checks continue to work.

Compare a single-agent baseline against coordinator-plus-reviewer on representative synthetic creation and review cases. Measure source fidelity, required-concept coverage, alignment, useful finding detection and false alarms, workflow compliance, completion, latency, and cost. Mocked tests validate mechanics; model-quality evaluation needs a separately authorized manual run using synthetic data. Set release criteria before that evaluation. Validate the four agreed specialist roles incrementally; role labels alone are not evidence of expertise. Team-supplied curriculum packages with expert benchmark reviews are a desirable later evaluation asset, not a release prerequisite.

Activate capabilities incrementally as acceptance criteria pass. Replace the old workflow directly; a parallel legacy path is not required. Show accurate capability limitations during transition. Define recovery paths for ingestion, retrieval, generation, and export failures.

Develop on `dev`. Before every implementation commit and push, review/update the README and UserTour together; record no-user-facing-change reviews where appropriate. When tour steps change, test keyboard dismissal/navigation, administrator/member variants, and small-screen layout. Do not merge into `main`.

## Open implementation choices

These do not block requirements review: retrieval/storage technology; supported upload formats and limits; precise artifact and delegation schemas; orchestration library; task budgets/concurrency limits; instruction management UI; slide-generation libraries; prototype reset or optional data migration; and same-model guidance-update controls. Resolve during implementation design with the actual framework corpus and existing application constraints.

## Next implementation milestone — retrieval-backed specialist review

This milestone reviews existing courses. Full curriculum creation and Moodle export remain later work. It supersedes earlier sequencing that deferred the agreed specialists indefinitely.

### 1. Repair and verify settings

The owner reports that settings have reverted to lorem ipsum placeholders. Treat this as an unresolved defect, not a confirmed root cause. Inspect persisted settings, rendering, defaults and migration behavior; restore meaningful functional controls and remove placeholder content. Rebuilding the settings UI is acceptable if necessary. Preserve existing credentials and valid configuration; never invent or reset settings to hide the issue. Verify save/reload persistence, administrator/member permissions and the connection between the selected instructional model and new workspaces. Existing workspace models remain immutable. Include regression coverage and matching tour/README updates.

### 2. Store and retrieve evidence

Preserve originals and immutable revisions; index sections/passages with stable citations and page locations where extraction supports them. Add ingestion status, extraction failure reporting and index-version tracking. Administrators publish shared reference libraries; builders upload workspace evidence. Keep curriculum evidence, shared references and pinned instructional-model guidance distinguishable, with authority/version metadata. References inform review; they do not silently override owner-verified requirements.

Provide assignment-scoped search and passage/section reading. Retrieve initial task evidence when the ISD delegates, then permit specialists to request more within their authorized scope. Enforce workspace and published-library access in the backend. Pin document/library versions per review; later publication must not silently alter a running review. Treat retrieved text as evidence, never as instructions granting tools or permissions. Keep external discovery out of this milestone; existing inclusion-approval policy still applies if introduced later.

Replace the all-sources request and fixed 140,000-character workspace rejection with token-budgeted requests and staged processing. Reserve room for instructions, tool results and output. Oversized sections require smaller processing units, never silent omission. Preserve the full transcript separately; supply recent conversation, working summaries and owner-verified state without promoting summaries into established state.

### 3. Track scope and review coverage

Default to full-course review. The builder may request narrow or quick review through chat. Record the scope and communicate coverage limits. Full review must account for every in-scope source section and required cross-document alignment check. Retrieval hits alone do not count as complete review. Track inspected, pending, unreadable, failed and excluded material against exact revisions, with applicable reviewer/check coverage. Surface unsupported media and extraction limitations.

Quick review is preliminary screening and cannot support full-course approval. Narrow review conclusions apply only to its recorded scope. Missing coverage or failed required tasks prevents a complete-review claim; material gaps continue to block approval. Source changes invalidate affected coverage and results without themselves changing established instructional decisions.

### 4. Implement controlled specialist execution

Extend the existing task model with parent/child assignments, scope, role, instruction versions, pinned evidence references, coverage obligations, allowed retrieval tools, status and resource usage. Persist tasks before execution; support bounded retries, cancellation and restart recovery without duplicate findings/comments. Specialists return structured evidence-linked findings, confidence rationale, limitations, coverage, disagreements and proposed anchored comments. They cannot approve, modify established state or execute uploaded code.

Run independent analysis, one challenge round and bounded targeted verification. The ISD decides which roles are relevant and may use multiple SMEs after confirming subject areas with the builder. Enforce concurrency, token, time and retry limits in application code. When a limit prevents completion, show incomplete status and the next available action; do not imply the review passed.

### 5. Present one coherent review

Log each delegation in chat in plain language, naming the specialist role and task. Show meaningful completion, failure and required-owner-action updates without flooding chat with internal exchanges. Preserve specialist findings and task records for on-demand inspection, separately from consequential project history. Never store private model reasoning.

The ISD synthesizes one strengths-and-gaps report with source-linked findings, per-document confidence/readiness, review scope and coverage, unresolved conflicts, and peer-review recommendations. Retain anchored comments for owner resolution. Consequential disagreements require builder disposition; declining peer review or resolving a comment does not clear an underlying material blocker. Only owner-verified consequential changes enter established state/history.

### 6. Validate and release incrementally

Use synthetic documents and mocked providers for automated tests. Cover large multi-document collections, citations and anchors, workspace isolation, pinned versions, injection attempts in evidence, empty retrieval, extraction failures, partial coverage, revision changes, independent/challenge sequencing, conflicting findings, static-only inspection, budgets, cancellation and recovery. Verify settings persistence and chat delegation logs, administrator/member variants, keyboard behavior and mobile layout.

Release gates: no silent source loss; no false full-review claims; traceable findings; enforced permissions and approval boundaries; bounded/recoverable delegation; functional persistent settings. Mocked tests verify mechanics, not educational quality. Arrange a separately authorized manual review with educators before broad rollout and explicitly record quality limitations. A team-authored benchmark corpus remains nice to have, not a release gate.

### Educator contributions and remaining engineering choices

Invite the team to refine each role's review checklist, identify authoritative shared references and examine sample findings for usefulness and false alarms. Expert benchmark packages may follow later. The agreed baseline above is sufficient to begin technical design; team input must not be presented as already supplied.

Choose retrieval/storage technology, passage sizing, numeric execution budgets and supported-format limits after inspecting available infrastructure and representative documents. Use reversible defaults and document them; ask the owner when a choice materially changes scope, cost, privacy or workflow. The owner subsequently authorized implementation and a reset of existing prototype workspaces; see the progress record for completed work and retained data.

Next checkpoint: review the implemented specialist workflow with the educators, using a newly created workspace and the available framework/reference documents. Confirm live-model usefulness and remaining evidence limitations before broadening scope to course creation. See IMPLEMENTATION_PROGRESS.md for validation and runtime boundaries.
