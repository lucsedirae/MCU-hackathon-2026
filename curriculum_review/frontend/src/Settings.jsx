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
  const [systemPrompt, setSystemPrompt] = useState('');
  const [guardrailsPrompt, setGuardrailsPrompt] = useState('');
  const [reviewInstructions, setReviewInstructions] = useState({ review_rubric: '', evidence_rules: '', examples: '' });
  const [busy, setBusy] = useState('load');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  function apply(data) {
    setSaved(data);
    setModel(data.model);
    setKey('');
    setSystemPrompt(data.system_prompt || '');
    setGuardrailsPrompt(data.guardrails_prompt || '');
    setReviewInstructions({ review_rubric: data.review_rubric || '', evidence_rules: data.evidence_rules || '', examples: data.examples || '' });
  }

  useEffect(() => {
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

  const dirty = saved && (model !== saved.model || key !== '' || systemPrompt !== (saved.system_prompt || '') || guardrailsPrompt !== (saved.guardrails_prompt || '') || Object.entries(reviewInstructions).some(([field, value]) => value !== (saved[field] || '')));

  async function act(action) {
    setBusy(action);
    setNotice('');
    setError('');
    try {
      if (action === 'save' || (action === 'test' && dirty)) {
        const data = await api('/api/settings/llm', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, api_key: key || null, system_prompt: systemPrompt, guardrails_prompt: guardrailsPrompt, ...reviewInstructions }),
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
          <details className="prompt-settings"><summary>Review instructions</summary>
            <h2 id="prompt-settings-title">System instructions</h2>
            <label className="chat-label" htmlFor="system-prompt">System prompt</label>
            <textarea id="system-prompt" className="chat-input" rows={6} maxLength={32000} value={systemPrompt} onChange={event => setSystemPrompt(event.target.value)} placeholder="Describe the agent’s role, goals, and response style…" />
            <label className="chat-label" htmlFor="guardrails-prompt">Guardrails prompt</label>
            <textarea id="guardrails-prompt" className="chat-input" rows={5} maxLength={32000} value={guardrailsPrompt} onChange={event => setGuardrailsPrompt(event.target.value)} placeholder="Describe boundaries and rules the agent should follow…" aria-describedby="guardrails-help" />
            <p id="guardrails-help" className="chat-hint">Guardrails guide the model; they do not guarantee enforcement.</p>
            {[
              ['review_rubric', 'Review rubric', 'Define review criteria, scoring levels, and what a successful curriculum should demonstrate…'],
              ['evidence_rules', 'Evidence rules', 'Describe how to cite source materials, distinguish assumptions, and handle missing evidence…'],
              ['examples', 'Examples', 'Add sample inputs and ideal reviews to demonstrate the expected approach, tone, and level of detail…'],
            ].map(([field, label, placeholder]) => (
              <div key={field}>
                <label className="chat-label" htmlFor={field}>{label}</label>
                <textarea id={field} className="chat-input" rows={6} maxLength={32000} value={reviewInstructions[field]} onChange={event => setReviewInstructions(previous => ({ ...previous, [field]: event.target.value }))} placeholder={placeholder} />
              </div>
            ))}
            <p className="chat-hint">All instruction fields are optional and included in model requests after saving.</p>
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
