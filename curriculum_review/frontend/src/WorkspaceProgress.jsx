import { useEffect, useState } from 'react';
import { api } from './api';

export default function WorkspaceProgress({ workspace }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    if (!workspace?.builder_mode) return;
    let active = true, timer;
    async function refresh() {
      try {
        const next = await api(`/builder/workspaces/${workspace.id}/progress`);
        if (active) { setData(next); setError(''); }
      } catch (e) { if (active) setError('Progress could not be refreshed. Retrying…'); }
      finally { if (active) timer = setTimeout(refresh, 3000); }
    }
    refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [workspace?.id, workspace?.builder_mode]);
  const tasks = data?.tasks || workspace?.runs || [];
  const latest = tasks[0];
  return <section className="workspace-progress" aria-label="Curriculum progress">
    <p className="eyebrow">Curriculum progress</p>
    <h2>{workspace?.title || 'Your next course'}</h2>
    {!workspace ? <p>Choose or create a workspace to begin.</p> : <>
      <p role="status">{error || (workspace.builder_mode && !data ? 'Loading progress…' : latest ? `Latest task: ${latest.status.replaceAll('_', ' ')}` : 'Ready for intake') }</p>
      {data && <p>{data.model} · {data.framework_ready ? 'Guidance connected' : 'Waiting for published guidance'}</p>}
      {latest?.coverage?.total > 0 && <p>{latest.coverage.examined} of {latest.coverage.total} passages examined ({latest.coverage.scope}). {latest.coverage.complete ? 'Scoped coverage complete.' : 'Coverage incomplete or preliminary.'}</p>}
      <p className="chat-hint">Recorded work, not curriculum approval. Confirmed decisions remain in workspace history.</p>
      <details open><summary>Analysis steps ({data?.events?.length || 0})</summary>
        <ol className="progress-timeline">{data?.events?.map(e => <li key={e.id}><time dateTime={e.created}>{new Date(e.created).toLocaleString()}</time><p>{e.text}</p></li>)}</ol>
        {data && !data.events?.length && <p>No analysis steps recorded yet.</p>}
      </details>
      {!!tasks.length && <details><summary>Task history ({tasks.length})</summary><ol className="progress-timeline">{tasks.map(t => <li key={t.id}><time dateTime={t.created}>{new Date(t.created).toLocaleString()}</time><p>{t.action || t.kind} · {t.status.replaceAll('_', ' ')}</p></li>)}</ol></details>}
    </>}
  </section>;
}
