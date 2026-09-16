import { useEffect, useRef, useState } from 'react';

// Keep these steps aligned with README.md whenever committing/pushing to dev.
export const TOUR_REVIEWED = '2026-09-16';
const steps = [
  { title: 'Welcome to Cadence', text: 'Use this tool to read a curriculum, discuss improvements, review proposed changes, and keep a complete version history.', tip: 'This tour is a guide only: it does not upload files, change settings, or start paid AI requests.' },
  { title: 'Choose a workspace', text: 'Open Workspaces and choose a curriculum from the left sidebar. Each workspace has an owner. Everyone on the team can read and comment; only the owner can upload, run reviews, and accept changes.', tip: 'Administrators create workspaces and assign or transfer ownership. Being an administrator does not automatically make you the owner.' },
  { title: 'Find your way around', text: 'Curriculum shows the current document. Proposals collects pending and rejected changes. Reports contains review findings. Activity shows review and generation jobs, their source versions, results, and transcripts.', tip: 'When no curriculum has been accepted yet, opening the workspace may show its first proposal.' },
  { title: 'Add a curriculum', text: 'If you own the workspace, upload a file in the empty curriculum view, or choose Revise to upload a new proposal or generate one from instructions.', tip: 'Accepted uploads: Word, text-based PDF, Markdown, plain text, Moodle MBZ, and SCORM/Tin Can/cmi5 ZIP packages. The limit is 20 MB. Read import limitations: interactive or script-generated course content may be incomplete.' },
  { title: 'Read and comment', text: 'Open Comments. Select text in a paragraph or table cell to attach feedback, or use General comment. Expand a thread to reply. Show passage jumps to the relevant text; the original-context link shows the version where a comment began.', tip: 'Filter by Open, Resolved, Needs placement, or All. Comment authors and workspace owners can resolve or reopen threads. On mobile, Back to document returns from the comments panel to reading.' },
  { title: 'Ask for an AI review', text: 'As the owner, open the version you want reviewed and select Review. Add instructions and choose Start review. You can review accepted content or a proposal.', tip: 'An administrator must configure OpenAI first. Starting a review sends document text to OpenAI and may incur API charges. The report appears in Reports; progress and the transcript appear in Activity.' },
  { title: 'Create a revised proposal', text: 'Select Revise to upload a replacement or generate a proposal. To address feedback, check Address in next generated proposal on open curriculum comments, then choose Revise using selected comments.', tip: 'Generation creates a proposal. It never automatically replaces the accepted curriculum. Instructions apply to the version you are currently viewing.' },
  { title: 'Preview before accepting', text: 'Open a proposal, read 1. Preview document, then choose 2. Review changes. Changes load against the current accepted curriculum. The owner can accept the entire proposal or reject it, and optionally resolve the comments it addressed.', tip: 'Acceptance replaces the whole curriculum. An outdated-base warning means the proposal began from an older version. If the accepted version changes, load a fresh comparison before accepting. Rejected proposals remain available and can be reopened.' },
  { title: 'Use reports and activity', text: 'Reports support comments and version history. Owners can upload report revisions, which become current immediately. Activity lets you open the source curriculum, report, generated proposal, or permanent transcript for each job.', tip: 'Owners can stop a running job. Stopping prevents a late result from being applied, but may not stop provider processing or billing. Transcripts are read-only.' },
  { title: 'History and downloads', text: 'History lets you select earlier versions, compare revisions, restore content, and retrieve exact previously generated exports. Download offers Word, Markdown, original uploads, and an option to include unresolved comments.', tip: 'Restoring a curriculum creates a proposal for preview and acceptance. Restoring a report creates a new current revision. Older versions are retained.' },
  { title: 'Configure OpenAI and system prompts', admin: true, text: 'Open Administration → OpenAI settings. Save your API key, select a model from the dropdown, then save and test the connection. Expand System prompt & review instructions for System prompt, Guardrails prompt, Review rubric, Evidence rules, and Examples.', tip: 'Instructional Model currently shows ADDIE as a placeholder only; it does not affect reviews or generation. The shared instruction fields are optional. Save settings after editing them. Save and test connection saves changes before sending a small test request. Keys remain encrypted on the server.' },
  { title: 'Manage your team', admin: true, text: 'Open Administration → Team accounts to create accounts or reset passwords. Use Create a workspace in the sidebar to assign an owner, and Transfer ownership in a workspace to change that owner.', tip: 'Temporary passwords must have at least 8 characters. New users must change their temporary password when signing in.' },
  { title: 'You are ready', text: 'Start by choosing a workspace and reading its curriculum. Your user menu contains My account and Sign out. You can reopen User tour from the header at any time.', tip: 'Need the same instructions outside the app? See the User tour section in the project README.' },
];

export default function UserTour({ admin, onClose }) {
  const [index, setIndex] = useState(0);
  const dialog = useRef(null);
  const heading = useRef(null);
  const available = steps.filter(step => !step.admin || admin);
  const step = available[index];

  useEffect(() => {
    dialog.current.showModal();
  }, []);
  useEffect(() => { heading.current?.focus(); }, [index]);

  return (
    <dialog ref={dialog} className="user-tour" aria-labelledby="tour-title" onCancel={event => { event.preventDefault(); onClose(); }}>
      <div className="panel-heading">
        <p className="eyebrow">User tour · {index + 1} of {available.length}</p>
        <button className="secondary-button" onClick={onClose} aria-label="Close user tour">Close</button>
      </div>
      <progress value={index + 1} max={available.length} aria-label="Tour progress" />
      <h2 id="tour-title" ref={heading} tabIndex={-1}>{step.title}</h2>
      <p>{step.text}</p>
      <p className="notice">{step.tip}</p>
      <label className="field">Jump to a topic
        <select value={index} onChange={event => setIndex(Number(event.target.value))}>
          {available.map((item, i) => <option key={item.title} value={i}>{i + 1}. {item.title}</option>)}
        </select>
      </label>
      <div className="toolbar">
        <button className="secondary-button" disabled={index === 0} onClick={() => setIndex(index - 1)}>Back</button>
        {index < available.length - 1 ? <button onClick={() => setIndex(index + 1)}>Next</button> : <button onClick={onClose}>Finish tour</button>}
      </div>
    </dialog>
  );
}
