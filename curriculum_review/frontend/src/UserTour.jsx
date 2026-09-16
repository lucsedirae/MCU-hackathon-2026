import { useEffect, useRef, useState } from 'react';

// Reviewed sidebar progress, navigation, settings placement and mobile layout.
// Reviewed 2026-09-16: staged builder, pinned guidance, owner verification, chat-first flow.
// Reviewed formatted agent responses; existing tour actions and navigation remain accurate.
// Reviewed 1 GB Moodle uploads and removal of the extracted-text cap; existing tour wording remains accurate.
// Reviewed removal of the duplicate System instructions model selector.
// Reviewed 2026-09-16: short conversational replies for review and creation intake; detailed evidence stays in task records and reports.
// Reviewed specialist delegation, scoped evidence, shared references, active instructions and review limits.
export const TOUR_REVIEWED = '2026-09-16';
const steps = [
  { title: 'Welcome to Cadence', text: 'Use this tool to read a curriculum, discuss improvements, review proposed changes, and keep a complete version history.', tip: 'This tour is a guide only: it does not upload files, change settings, or start paid AI requests.' },
  { title: 'Choose a workspace', text: 'Open Workspaces and choose a curriculum from the left sidebar. Each workspace has an owner. Everyone on the team can read and comment; only the owner can upload, run reviews, and accept changes.', tip: 'Any signed-in builder can choose Start course builder and owns the new workspace. Administrators can still create legacy workspaces or transfer ownership.' },
  { title: 'Use the course builder', text: 'Start course builder creates a review or creation-intake workspace. Use Conversation to attach or drop documents, type a message, and select Send. The ISD leads intake and delegates to SMEs, assessment, exercise, and technical/accessibility specialists as needed. Delegations appear in chat; findings and evidence are available under Task activity. Workspace details in the sidebar holds files, history, and the pinned guidance version while Conversation is open.', tip: 'Full review is the default; ask in chat for a narrow review or quick screening. Quick screening cannot be approved as a complete review. Material gaps block approval. Review and creation intake use short conversational replies: what was checked or done, then a useful next step or one question. Ask for more detail when needed. Answer in chat to work through gaps. Detailed reports and confirmation requests remain available. Open the report and source comments, then explicitly confirm only consequential changes. Published guidance connects automatically; missing documentation is an administrator dependency. Report approval and comment resolution are separate. Full course production and external research are not enabled yet.' },
  { title: 'Find your way around', text: 'The sidebar records analysis steps above Navigation and settings. These activity records do not approve curriculum or change established decisions. On small screens the sidebar appears above the conversation; collapse Navigation and settings to save space. Curriculum shows the current document. Proposals collects pending and rejected changes. Reports contains review findings. Activity shows review and generation jobs, their source versions, results, and transcripts.', tip: 'When no curriculum has been accepted yet, opening the workspace may show its first proposal.' },
  { title: 'Add a curriculum', text: 'If you own the workspace, upload a file in the empty curriculum view, or choose Revise to upload a new proposal or generate one from instructions.', tip: 'Accepted uploads: Word, text-based PDF, Markdown, plain text, Moodle MBZ, and SCORM/Tin Can/cmi5 ZIP packages. Moodle backups can be up to 1 GB; other files are limited to 20 MB. Read import limitations: interactive or script-generated course content may be incomplete.' },
  { title: 'Read and comment', text: 'Open Comments. Select text in a paragraph or table cell to attach feedback, or use General comment. Expand a thread to reply. Show passage jumps to the relevant text; the original-context link shows the version where a comment began.', tip: 'Filter by Open, Resolved, Needs placement, or All. In legacy workspaces, comment authors and owners can resolve threads. Builder review comments require the owner. On mobile, Back to document returns from the comments panel to reading.' },
  { title: 'Ask for an AI review', text: 'As the owner, open the version you want reviewed and select Review. Add instructions and choose Start review. You can review accepted content or a proposal.', tip: 'An administrator must configure OpenAI first. Starting a review sends document text to OpenAI and may incur API charges. The report appears in Reports; progress and the transcript appear in Activity.' },
  { title: 'Create a revised proposal', text: 'Select Revise to upload a replacement or generate a proposal. To address feedback, check Address in next generated proposal on open curriculum comments, then choose Revise using selected comments.', tip: 'Generation creates a proposal. It never automatically replaces the accepted curriculum. Instructions apply to the version you are currently viewing.' },
  { title: 'Preview before accepting', text: 'Open a proposal, read 1. Preview document, then choose 2. Review changes. Changes load against the current accepted curriculum. The owner can accept the entire proposal or reject it, and optionally resolve the comments it addressed.', tip: 'Acceptance replaces the whole curriculum. An outdated-base warning means the proposal began from an older version. If the accepted version changes, load a fresh comparison before accepting. Rejected proposals remain available and can be reopened.' },
  { title: 'Use reports and activity', text: 'Reports support comments and version history. Owners can upload report revisions, which become current immediately. Activity lets you open the source curriculum, report, generated proposal, or permanent transcript for each job.', tip: 'Owners can stop a running job. Stopping prevents a late result from being applied, but may not stop provider processing or billing. Transcripts are read-only.' },
  { title: 'History and downloads', text: 'History lets you select earlier versions, compare revisions, restore content, and retrieve exact previously generated exports. Download offers Word, Markdown, original uploads, and an option to include unresolved comments.', tip: 'Restoring a curriculum creates a proposal for preview and acceptance. Restoring a report creates a new current revision. Older versions are retained.' },
  { title: 'Configure OpenAI and system prompts', admin: true, text: 'Open Administration → OpenAI settings. Save your API key, select a model from the dropdown, then save and test the connection. Open ISD instructions to inspect the active versioned instructions. Choose Model when uploading guidance in the framework library.', tip: 'New builder workspaces currently use ADDIE. Upload, inspect and publish ADDIE guidance in the framework library. Administrators can also upload, inspect and publish subject references in Shared reference library. Agent instructions are maintained with the application and shown read-only; there is no placeholder prompt editor. Save and test connection saves changes before sending a small test request. Keys remain encrypted on the server.' },
  { title: 'Manage your team', admin: true, text: 'Open Administration → Team accounts to create accounts or reset passwords. Use Create a workspace in the sidebar to assign an owner, and Transfer ownership in a workspace to change that owner.', tip: 'Temporary passwords must have at least 8 characters. New users must change their temporary password when signing in.' },
  { title: 'You are ready', text: 'Start by choosing a workspace and reading its curriculum. The sidebar contains your account menu, Sign out, and User tour below the workspace navigation.', tip: 'Need the same instructions outside the app? See the User tour section in the project README.' },
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
