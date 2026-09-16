import { createPortal } from "react-dom";
import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import AgentMessage from './AgentMessage';

export function FrameworkLibrary() {
  const [items, setItems] = useState([]), [selected, setSelected] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const reload = async () => setItems(await api('/frameworks'));
  useEffect(() => { reload().catch(e => setError(e.message)); }, []);
  async function act(fn) { setBusy(true); setError(''); try { await fn(); await reload(); } catch(e) { setError(e.message); } finally { setBusy(false); } }
  return <section className="panel"><h2>Instructional framework library</h2>
    <p>Upload the curated ADDIE guidance, inspect it, then publish an immutable version. No framework definition is supplied automatically. Each builder workspace pins its selected version.</p>
    <form aria-label="Upload framework guidance" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; act(async () => { const f = await api('/frameworks', {method:'POST', body:new FormData(form)}); setSelected(await api(`/frameworks/${f.id}`)); form.reset(); }); }}>
      <fieldset disabled={busy}><label className="field">Model<select aria-label="Model" name="model" required defaultValue="ADDIE"><option value="ADDIE">ADDIE</option></select></label><label className="field">Version label<input name="version" required maxLength={80}/></label><label className="field">Guidance document<input name="file" type="file" accept=".docx,.pdf,.md,.txt" required/></label><button>Upload for inspection</button></fieldset>
    </form>
    {error && <p role="alert">{error}</p>}
    {items.map(f => <p key={f.id}><button className="secondary-button" onClick={() => act(async () => setSelected(await api(`/frameworks/${f.id}`)))}>{f.title} · {f.version} · {f.published ? 'Published' : 'Draft'}</button></p>)}
    {selected && <section className="tool-panel"><h3>{selected.title} · {selected.version}</h3><div className="builder-preview">{selected.content.blocks.map(b => <p key={b.id}>{b.text || b.rows?.map(r=>r.join(' | ')).join('\n')}</p>)}</div>
      {!selected.published && <button disabled={busy} onClick={() => act(async () => { await api(`/frameworks/${selected.id}/publish`, {method:'POST'}); setSelected(await api(`/frameworks/${selected.id}`)); })}>Publish this guidance version</button>}</section>}
  </section>;
}

export function NewBuilder({ onCreated }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  return <details><summary>Start course builder</summary><form onSubmit={async e => {
    e.preventDefault(); const form = e.currentTarget; setBusy(true); setError('');
    try { const w = await api('/builder/workspaces', {method:'POST', body:Object.fromEntries(new FormData(form))}); await onCreated(w.id); form.reset(); form.closest("details").open = false; } catch(e) {setError(e.message);} finally {setBusy(false);}
  }}><fieldset disabled={busy}><label className="field">Workspace title<input name="title" required maxLength={200}/></label><label className="field">Purpose<select name="mode"><option value="review">Review existing curriculum</option><option value="creation">Create a course (intake only)</option></select></label><p>You will own this workspace. The Learning Expert will guide you through the next steps.</p><button>Create builder workspace</button></fieldset></form>{error && <p role="alert">{error}</p>}</details>;
}

export default function Builder({ workspace, owner, onDocument, onRefresh, sidebarTarget }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [text, setText] = useState('');
  const [attachments, setAttachments] = useState([]), [dragging, setDragging] = useState(false);
  const fileInput = useRef(null), bottom = useRef(null);
  const wid = workspace.id;
  async function reload() { const next = await api(`/builder/workspaces/${wid}`); setData(next); return next; }
  useEffect(() => {
    let active = true;
    (async()=>{
      if(owner) await api(`/builder/workspaces/${wid}/prepare`, {method:'POST'});
      const d = await api(`/builder/workspaces/${wid}`);
      if(active) setData(d);
    })().catch(e=>{if(active)setError(e.message);});
    return ()=>{active=false;};
  }, [wid, owner]);
  const running = data?.tasks.find(t=>t.status==='running');
  useEffect(() => {
    if(!running) return;
    const timer=setInterval(()=>reload().then(d=>{if(!d.tasks.some(t=>t.status==='running')) return onRefresh();}).catch(e=>setError(e.message)),2000);
    return ()=>clearInterval(timer);
  }, [wid, running?.id]);
  useEffect(()=>{bottom.current?.scrollIntoView({block:'nearest'});},[data?.entries.length]);
  async function act(fn) {
    if(busy) return;
    setBusy(true); setError('');
    try {await fn();await reload();await onRefresh();}
    catch(e){setError(e.message);await reload().catch(()=>{});}
    finally{setBusy(false);}
  }
  function attach(files) {
    if(!owner || busy || running) return;
    const incoming = Array.from(files);
    setAttachments(previous=>[...previous,...incoming]);
  }
  async function send(e) {
    e.preventDefault();
    const message=text.trim();
    if(!message&&!attachments.length) return;
    await act(async()=>{
      // Remove each successful upload from the queue so retries do not duplicate it.
      for(const file of attachments){
        const body=new FormData();body.append('file',file);
        await api(`/builder/workspaces/${wid}/sources`,{method:'POST',body});
        setAttachments(previous=>previous.filter(item=>item!==file));
      }
      await api(`/builder/workspaces/${wid}/chat`,{method:'POST',body:{
        text:message || 'I have uploaded my documents. Help me understand what they establish and what you need from me next.', action:'chat'
      }});
      setText('');
    });
  }
  if(!data) return <p role="status">{error || 'Loading conversation…'}</p>;
  const pending=data.proposals.filter(p=>p.status==='pending');
  const reports=data.tasks.filter(t=>t.result.report_id);
  return <section className="panel builder builder-chat">
    <div className="panel-heading"><div><h2>Learning Expert</h2><p>I’ll guide the instructional-design process, one step at a time.</p></div>
      {sidebarTarget && createPortal(<details className="builder-details"><summary>Workspace details</summary>
        <p>{data.model} · {data.framework ? `Guidance ${data.framework.version} (pinned)` : 'Waiting for framework guidance'}</p>
        {data.mode==='creation'&&<p>Creation currently supports intake; full course production is a later milestone.</p>}
        <h3>Documents</h3>{!data.sources.length&&<p>No documents attached yet.</p>}
        {data.sources.map(s=><div key={s.id}><button className="text-button" onClick={()=>onDocument(s.id,s.revision_id)}>{s.title}</button>{s.warnings.map((w,i)=><p key={i}>{w}</p>)}</div>)}
        {reports.map(t=><p key={t.id}><button className="text-button" onClick={()=>onDocument(t.result.report_id,t.result.report_revision_id)}>Review report</button></p>)}
        <h3>Confirmed changes</h3>{data.proposals.filter(p=>p.status==='verified').map(p=><p key={p.id}><strong>{p.title}</strong> — {p.disposition}</p>)}
        <details><summary>Task activity</summary>{data.tasks.map(t=><SpecialistActivity key={t.id} task={t}/>)}</details>
        <p><a href={`/api/builder/workspaces/${wid}/export`}>Download documents and history</a></p>
      </details>, sidebarTarget)}
    </div>
    <div className="builder-conversation" aria-label="Course conversation">
      <article className="chat-message assistant"><strong>Learning Expert</strong>
        <p>Upload your course materials, or tell me about the course and its learners. I’ll guide you through {data.mode==='review' ? 'the review' : 'course planning'} and ask for what’s missing.</p>
        {!data.framework&&<p className="chat-hint">You can share materials now. Instructional analysis is waiting for your administrator to publish the framework guidance; it will be connected automatically.</p>}
      </article>
      {data.entries.map(e=><article className={`chat-message ${e.role}`} key={e.id}><strong>{e.role==='user'?'You':e.role==='assistant'?'Learning Expert':'Workspace'}</strong>{e.role==='assistant'?<AgentMessage>{e.text}</AgentMessage>:<p className="preserve-text">{e.text}</p>}</article>)}
      {data.tasks.slice(0,1).filter(t=>['failed','stale','needs_revision','interrupted','incomplete'].includes(t.status)).map(t=><article className="chat-message system" key={t.id}><strong>Review update</strong><p>{t.error || 'The quality check found issues. Ask me to revise the review before you approve it.'}</p></article>)}
      {reports.slice(0,1).map(t=><article className="chat-message assistant" key={t.id}>
        <strong>Review report</strong><p>{t.result.quality?.rationale}</p><SpecialistActivity task={t}/><p>Evidence confidence: {t.result.quality?.confidence}. {t.result.quality?.peer_review}</p>
        <button className="secondary-button" onClick={()=>onDocument(t.result.report_id,t.result.report_revision_id)}>Read report</button>
        {t.result.approval ? <p>{t.approval_current?'You approved this report.':'Your earlier approval is retained; the evidence or report has changed.'}</p> : owner&&(t.result.material_blockers || !t.result.coverage?.complete) ? <p>Approval is unavailable while material issues or incomplete coverage remain. Quick reviews are preliminary.</p> : owner&&<details><summary>Review and approve</summary><p>This approves the report, not the curriculum it assesses.</p>
          <form onSubmit={e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.currentTarget));act(()=>api(`/builder/tasks/${t.id}/approve-report`,{method:'POST',body:{...values,revision_id:t.result.report_revision_id}}));}}>
            <label className="field">Peer review<select name="peer_review"><option value="requested">Requested</option><option value="completed">Completed</option><option value="declined">Declined</option></select></label>
            <label className="field">Your review or decline reason<input name="reason" required maxLength={4000}/></label><button disabled={busy}>Approve report</button>
          </form></details>}
      </article>)}
      {pending.map(p=><article className="chat-message confirmation" key={p.id}><strong>Your confirmation is needed</strong><h3>{p.title}</h3><p>{p.rationale}</p><p>What this affects: {p.impact}</p>
        {owner&&<details><summary>Confirm or decline this change</summary><form onSubmit={e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.currentTarget));act(()=>api(`/builder/proposals/${p.id}/verify`,{method:'POST',body:{...values,expected_state_version:data.state_version}}));}}>
          <label className="field">Decision<select name="decision"><option value="verify">Confirm change</option><option value="decline">Decline change</option></select></label><label className="field">Reason<input name="reason" required maxLength={4000}/></label><button disabled={busy}>Confirm decision</button>
        </form></details>}
      </article>)}
      {running&&<p role="status">Learning Expert is working… {owner&&<button className="text-button" onClick={()=>act(()=>api(`/builder/tasks/${running.id}/stop`,{method:'POST'}))}>Stop</button>}</p>}
      <div ref={bottom}/>
    </div>
    {error&&<p role="alert" className="settings-error">{error}</p>}
    {owner&&<form className={`chat-composer ${dragging?'dragging':''}`} onSubmit={send}
      onDragOver={e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();setDragging(true);}}}
      onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);attach(e.dataTransfer.files);}}>
      <label className="field">Message<textarea value={text} onChange={e=>setText(e.target.value)} maxLength={12000} rows={3} placeholder="Tell me about your course, ask a question, or drop documents here…"/></label>
      {attachments.length>0&&<ul className="chat-attachments">{attachments.map((f,i)=><li key={i}>{f.name}<button type="button" className="text-button" aria-label={`Remove ${f.name}`} disabled={busy} onClick={()=>setAttachments(previous=>previous.filter((_,index)=>index!==i))}>Remove</button></li>)}</ul>}
      <input ref={fileInput} type="file" multiple accept=".docx,.pdf,.md,.txt,.mbz,.zip" hidden aria-label="Attach documents" onChange={e=>{attach(e.target.files);e.target.value='';}}/>
      <div className="toolbar"><button type="button" className="secondary-button" disabled={busy||!!running} onClick={()=>fileInput.current.click()}>Attach documents</button><button disabled={busy||!!running||(!text.trim()&&!attachments.length)}>{busy?'Sending…':'Send'}</button></div>
      <p className="chat-hint">Moodle backups: up to 1 GB. Other files: up to 20 MB. When AI guidance is available, messages and source text are sent to your configured model and may incur charges.</p>
    </form>}
  </section>;
}

function SpecialistActivity({ task }) {
  const [items,setItems]=useState(null), [error,setError]=useState(''), [evidence,setEvidence]=useState(null);
  async function load(){try{setItems(await api(`/builder/tasks/${task.id}/specialists`));}catch(e){setError(e.message);}}
  return <details className="specialist-findings" onToggle={e=>{if(e.currentTarget.open)load();}}><summary>Specialist findings · {task.status}</summary>
    {task.result.coverage&&<p>{task.result.coverage.scope} review: {task.result.coverage.examined} of {task.result.coverage.total} indexed text passages examined. {task.result.coverage.complete?'Scoped text coverage complete.':'Review coverage incomplete or preliminary.'}</p>}
    {error&&<p role="alert">{error}</p>}
    {items?.map(c=><details key={c.id}><summary>{c.role} · {c.assignment.subject} · {c.stage} · {c.status}</summary>
      <p>{c.assignment.objective}</p><p>{c.error||c.result.summary}</p>
      {c.result.confidence&&<p>Confidence: {c.result.confidence}. {c.result.rationale}</p>}
      {c.result.limitations?.map((x,i)=><p key={i}>{x}</p>)}
      {c.result.findings?.map((f,i)=><section key={i}><h4>{f.title}</h4><p>{f.explanation}</p><p>{f.recommendation}</p>{f.material&&<p>Material issue: owner attention required.</p>}{f.citations.map(pid=><button key={pid} className="text-button" onClick={async()=>{try{setEvidence(await api(`/builder/tasks/${task.id}/evidence/${pid}`));}catch(e){setError(e.message);}}}>Read evidence {pid.slice(0,8)}</button>)}</section>)}
    </details>)}
    {evidence&&<blockquote><strong>{evidence.title || evidence.collection}</strong><p>{evidence.text}</p><small>{evidence.page ? `Page ${evidence.page} · ` : ''}{evidence.collection} · version {evidence.version_id} · block {evidence.block_id} · offset {evidence.start}</small></blockquote>}
  </details>;
}
