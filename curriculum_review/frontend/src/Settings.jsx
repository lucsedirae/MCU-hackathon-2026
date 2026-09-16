import { useEffect, useState } from 'react';

async function api(path, options) {
  const response = await fetch(path, { ...options, signal: AbortSignal.timeout(70000) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the connection fields and try again.');
  return data;
}

export default function Settings() {
  const [saved, setSaved] = useState(null);
  const [model, setModel] = useState('');
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState('');
  const [modelsRefresh, setModelsRefresh] = useState(0);
  const [key, setKey] = useState('');
  const [instructions, setInstructions] = useState([]);
  const [busy, setBusy] = useState('load');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  function apply(data) {
    setSaved(data);
    setModel(data.model);
    setKey('');
  }

  useEffect(() => {
    api('/api/builder/instructions').then(setInstructions).catch(()=>setError('Could not load active instructions. Refresh to try again.'));
    api('/api/settings/llm').then(apply).catch(() => setError('Could not load settings. Refresh the page to try again.')).finally(() => setBusy(''));
  }, []);

  useEffect(() => {
    let active = true;
    setModels([]);
    setModelsError('');
    if (!saved?.has_api_key) {
      setModelsLoading(false);
      return;
    }
    setModelsLoading(true);
    api('/api/settings/llm/models')
      .then(data => { if (active) setModels(data.models); })
      .catch(error => { if (active) setModelsError(error.message); })
      .finally(() => { if (active) setModelsLoading(false); });
    return () => { active = false; };
  }, [saved, modelsRefresh]);

  const dirty = saved && (model !== saved.model || key !== '');

  async function act(action) {
    setBusy(action);
    setNotice('');
    setError('');
    try {
      if (action === 'save' || (action === 'test' && dirty)) {
        const data = await api('/api/settings/llm', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, api_key: key || null }),
        });
        apply(data);
        setNotice('Settings saved.');
      }
      if (action === 'test') {
        const data = await api('/api/settings/llm/test', { method: 'POST' });
        setNotice(data.message);
      } else if (action === 'disconnect') {
        await api('/api/settings/llm', { method: 'DELETE' });
        apply({ base_url: 'https://api.openai.com/v1', model: '', has_api_key: false });
        setNotice('Connection removed.');
      }
    } catch (error) {
      setError(error.name === 'TimeoutError' ? 'The request timed out. Please try again.' : error.message || 'Unable to reach the backend.');
    } finally {
      setBusy('');
    }
  }

  return (
    <section className="panel settings-panel" aria-labelledby="settings-title">
      <p className="eyebrow">Settings</p>
      <h1 id="settings-title">OpenAI connection</h1>
      <p className="addie-description">Connect OpenAI for curriculum generation and review.</p>
      <p className="connection-badge">{saved?.has_api_key ? 'API key saved' : 'No API key saved'}</p>
      <form onSubmit={event => { event.preventDefault(); act('save'); }}>
        <fieldset disabled={!!busy || !saved}>
          <label className="chat-label" htmlFor="llm-model">Model</label>
          <select className="settings-input" id="llm-model" value={model} onChange={event => setModel(event.target.value)} disabled={modelsLoading || !saved?.has_api_key} aria-describedby="model-help">
            <option value="">{modelsLoading ? 'Loading models…' : 'Select a model'}</option>
            {model && !models.includes(model) && <option value={model}>{model} (current selection)</option>}
            {models.map(id => <option key={id} value={id}>{id}</option>)}
          </select>
          <p id="model-help" className="chat-hint">{!saved?.has_api_key ? 'Save your API key to load models, then select a model and save again.' : 'Text model options from your saved OpenAI key. Use Test connection to confirm compatibility.'}</p>
          <button type="button" className="secondary-button" disabled={!saved?.has_api_key || modelsLoading || key !== ''} onClick={() => setModelsRefresh(value => value + 1)}>Refresh models</button>
          {key !== '' && <p className="chat-hint">Save the new key to update the model list.</p>}
          {modelsError && <p className="settings-error" role="alert">{modelsError}</p>}
          {saved?.has_api_key && !modelsLoading && !modelsError && models.length === 0 && <p className="chat-hint">No matching text models were found for this key.</p>}
          <label className="chat-label" htmlFor="llm-key">API key</label>
          <input className="settings-input" id="llm-key" type="password" autoComplete="new-password" spellCheck={false} maxLength={8192} value={key} onChange={event => setKey(event.target.value)} placeholder={saved?.has_api_key ? 'Leave blank to keep your saved key' : 'Enter API key'} aria-describedby="key-help" />
          <p id="key-help" className="chat-hint">Encrypted on the server and used only with OpenAI. Enter a new key to replace it.</p>
          <details className="prompt-settings" open><summary>ISD instructions</summary>
            <h2 id="prompt-settings-title">System instructions</h2>
            <h3>Active agent instructions</h3>
            <p className="chat-hint">These versioned instructions control the ISD and specialists. They are maintained with the application; the obsolete shared prompt field is no longer used by the builder.</p>
            {instructions.map(item=><details key={item.role}><summary>{item.role} · {item.version.slice(0,12)}</summary><pre className="instruction-preview">{item.text}</pre></details>)}
          </details>
          <div className="settings-actions">
            <button type="submit">{busy === 'save' ? 'Saving…' : 'Save settings'}</button>
            <button type="button" disabled={!model || (!saved?.has_api_key && !key.trim())} onClick={() => act('test')}>{busy === 'test' ? 'Testing…' : dirty ? 'Save and test connection' : 'Test connection'}</button>
            <button className="secondary-button" type="button" disabled={!saved?.has_api_key} onClick={() => act('disconnect')}>Disconnect</button>
          </div>
        </fieldset>
      </form>
      <p className="chat-hint">All fields are optional when saving. Select a model and provide an API key to test. Unsaved changes are saved before testing. The test sends a short prompt and may incur a small OpenAI charge.</p>
      {busy === 'load' && <p role="status">Loading settings…</p>}
      {notice && <p className="settings-notice" role="status">{notice}</p>}
      {error && <p className="settings-error" role="alert">{error}</p>}
    </section>
  );
}
