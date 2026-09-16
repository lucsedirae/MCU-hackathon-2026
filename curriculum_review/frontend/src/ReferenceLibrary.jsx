import { useEffect, useState } from 'react';
import { api } from './api';

export default function ReferenceLibrary() {
  const [items,setItems]=useState([]), [selected,setSelected]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  const reload=async()=>setItems(await api('/references'));
  useEffect(()=>{reload().catch(e=>setError(e.message));},[]);
  async function act(fn){setBusy(true);setError('');try{await fn();await reload();}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <section className="panel"><h2>Shared reference library</h2>
    <p>Publish subject references for the ISD and specialists. Reviews retain the versions available when they start. Workspace uploads remain separate course evidence.</p>
    <form aria-label="Upload shared reference" onSubmit={e=>{e.preventDefault();const form=e.currentTarget;act(async()=>{const r=await api('/references',{method:'POST',body:new FormData(form)});setSelected(await api(`/references/${r.id}`));form.reset();});}}>
      <fieldset disabled={busy}>
        <label className="field">Reference title<input name="title" required maxLength={200}/></label>
        <label className="field">Subject area<input name="subject" required maxLength={200}/></label>
        <label className="field">Issuing authority<input name="authority" required maxLength={300}/></label>
        <label className="field">Reference version<input name="version" required maxLength={80}/></label>
        <label className="field">Source link (optional)<input name="source_url" type="url" maxLength={2000}/></label>
        <label className="field">Reference document<input name="file" type="file" required accept=".docx,.pdf,.md,.txt"/></label>
        <button>Inspect reference</button>
      </fieldset>
    </form>
    {error&&<p role="alert">{error}</p>}
    {items.map(r=><p key={r.id}><button className="secondary-button" onClick={()=>act(async()=>setSelected(await api(`/references/${r.id}`)))}>{r.title} · {r.version} · {r.published?'Published':'Draft'}</button></p>)}
    {selected&&<section className="tool-panel"><h3>{selected.title}</h3><p>{selected.subject} · {selected.authority}</p><div className="builder-preview">{selected.content.blocks.map(b=><p key={b.id}>{b.text||b.rows?.map(row=>row.join(' | ')).join('\n')}</p>)}</div>{!selected.published&&<button disabled={busy} onClick={()=>act(async()=>{await api(`/references/${selected.id}/publish`,{method:'POST'});setSelected(await api(`/references/${selected.id}`));})}>Publish reference</button>}</section>}
  </section>;
}
