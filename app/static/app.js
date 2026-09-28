const $ = (id) => document.getElementById(id);
const agents = [
  ['supervisor', 'Supervisor / Router', 'Understands intent & routes the query'],
  ['planning', 'Planning Agent', 'Breaks the question into clear steps'],
  ['retrieval', 'RAG / Retrieval Agent', 'Finds relevant document evidence'],
  ['tool', 'Tool Agent', 'Selects & runs the right tools'],
  ['execution', 'Execution Agent', 'Builds an answer from the evidence'],
  ['reflection', 'Reflection / Critic', 'Checks grounding & answer quality'],
];
let sessionId = localStorage.getItem('relay-session');
let activeRun = null, stream = null, lastRun = null, busy = false;
const selected = new Set();
const seenEvents = new Set();

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function notice(message, success = false) {
  $('notice').textContent = message;
  $('notice').className = `notice${success ? ' success' : ''}`;
  $('notice').hidden = false;
}
async function api(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body));
  return body;
}
function post(body) { return {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}; }
function resetTrace() {
  $('pipeline').replaceChildren(); $('events').replaceChildren(); $('sources').replaceChildren();
  $('events').append(el('p', 'empty-copy', 'Your agent trace will appear here. Every decision has a place.'));
  $('sources').append(el('p', 'empty-copy', 'Retrieved passages will appear here with similarity scores and page references.'));
  $('source-count').textContent = '0'; $('export').disabled = true; seenEvents.clear(); lastRun = null;
  agents.forEach(([key, name, description], index) => {
    const node = el('div', 'agent'); node.id = `agent-${key}`;
    node.append(el('span', 'agent-number', String(index + 1).padStart(2, '0')));
    const info = el('div', 'agent-info'); info.append(el('strong', '', name), el('small', '', description));
    node.append(info, el('span', 'agent-state', '—')); $('pipeline').append(node);
  });
}
function tab(sources) {
  $('agent-panel').hidden = sources; $('source-panel').hidden = !sources;
  $('tab-agents').setAttribute('aria-selected', String(!sources)); $('tab-sources').setAttribute('aria-selected', String(sources));
}
function renderSources(sources) {
  $('source-count').textContent = sources.length; $('sources').replaceChildren();
  if (!sources.length) $('sources').append(el('p', 'empty-copy', 'No document passages were used in this run.'));
  sources.forEach(s => {
    const card = el('article', 'source');
    card.append(el('div', 'source-title', `[${s.citation}] ${s.name}`), el('div', 'source-meta', `PAGE ${s.page} · CHUNK ${s.position + 1} · COSINE ${s.score.toFixed(3)}`), el('p', '', s.text));
    $('sources').append(card);
  });
}
function addEvent(event) {
  if (seenEvents.has(event.id)) return;
  seenEvents.add(event.id);
  $('events').querySelector('.empty-copy')?.remove();
  const node = $(`agent-${event.agent}`);
  if (node) {
    node.className = `agent ${event.status}`;
    node.querySelector('.agent-state').textContent = event.status === 'running' ? 'LIVE' : event.duration_ms !== undefined ? `${(event.duration_ms / 1000).toFixed(1)}s` : event.status;
  }
  if (event.status === 'running') $('run-status').textContent = `${agents.find(a => a[0] === event.agent)?.[1] || event.agent} is working…`;
  if (event.details?.sources) renderSources(event.details.sources);
  const details = el('details', 'event');
  const label = `${new Date(event.timestamp).toLocaleTimeString()} · ${event.agent} · ${event.status}`;
  details.append(el('summary', '', label), el('pre', '', JSON.stringify(event.details || {reason: event.reason}, null, 2)));
  $('events').append(details); $('events').scrollTop = $('events').scrollHeight;
}
function addMessage(role, content, rid) {
  $('welcome')?.remove();
  const node = el('article', `message ${role}`); const label = el('div', 'message-label', role === 'user' ? 'YOU' : 'RELAY');
  if (rid && role !== 'user') {
    const button = el('button', '', 'Inspect run ↗'); button.onclick = () => inspectRun(rid).catch(e => notice(e.message)); label.append(button);
  }
  node.append(label, el('div', 'message-body', content)); $('messages').append(node);
  $('messages').scrollTop = $('messages').scrollHeight;
  return node;
}
function setBusy(value) {
  busy = value; $('send').disabled = value; $('new-chat').disabled = value; $('query').disabled = value;
  $('trace-status').textContent = value ? 'RUNNING' : 'IDLE';
}
function completeRun(run, addAnswer = true) {
  stream?.close(); stream = null; activeRun = null; localStorage.removeItem('relay-active-run');
  lastRun = run; $('export').disabled = false;
  run.events.forEach(addEvent); renderSources(run.result?.sources || []); setBusy(false);
  $('trace-status').textContent = run.status.toUpperCase();
  $('run-status').textContent = run.status === 'completed' ? 'Answer reviewed · Run complete' : run.status === 'failed' ? 'Run failed · See the error below' : 'Review could not approve the answer';
  if (addAnswer) {
    const answer = run.result?.answer || run.result?.error || 'Run ended without a response.';
    const node = addMessage(run.status === 'failed' ? 'failed' : 'assistant', answer, run.id);
    if (run.result?.duration_ms) node.append(el('div', 'message-meta', `${run.result.model} · ${(run.result.duration_ms / 1000).toFixed(1)}s · ${run.result.sources.length} sources${run.result.revised ? ' · revised after critique' : ''}`));
  }
  $('query').focus();
}
function watchRun(rid) {
  activeRun = rid; localStorage.setItem('relay-active-run', rid); setBusy(true);
  stream?.close(); stream = new EventSource(`/api/runs/${rid}/events`);
  stream.addEventListener('trace', e => addEvent(JSON.parse(e.data)));
  stream.addEventListener('done', e => completeRun(JSON.parse(e.data)));
  stream.onerror = async () => {
    $('run-status').textContent = 'Reconnecting to the run…';
    try { const run = await api(`/api/runs/${rid}`); if (!['queued', 'running'].includes(run.status)) completeRun(run); }
    catch (e) { notice(`Connection interrupted: ${e.message}. Refresh to reconnect to this run.`); }
  };
}
async function inspectRun(rid) {
  if (busy) { notice('Wait for the active run to finish before inspecting an earlier run.'); return; }
  const run = await api(`/api/runs/${rid}`); resetTrace(); completeRun(run, false); tab(false);
}
async function loadDocuments() {
  const docs = await api('/api/documents');
  const ids = new Set(docs.map(d => d.id)); for (const id of selected) if (!ids.has(id)) selected.delete(id);
  $('doc-count').textContent = docs.length; $('documents').replaceChildren();
  if (!docs.length) $('documents').append(el('div', 'empty-library', 'A little context goes a long way. Upload your first document to get started.'));
  docs.forEach(d => {
    const row = el('div', 'doc'); const line = el('label', 'doc-line'); const input = el('input'); input.type = 'checkbox'; input.checked = selected.has(d.id);
    input.onchange = () => input.checked ? selected.add(d.id) : selected.delete(d.id);
    line.append(input, el('span', 'doc-name', d.name)); row.append(line, el('div', 'doc-meta', `${d.pages} page${d.pages === 1 ? '' : 's'} · ${d.chunks} chunks`));
    const actions = el('div', 'doc-actions'); const view = el('button', 'text-button', 'Inspect chunks');
    view.onclick = async () => {
      try {
        const chunks = await api(`/api/documents/${d.id}/chunks`); $('chunk-title').textContent = d.name; $('chunk-content').replaceChildren();
        chunks.forEach(c => { $('chunk-content').append(el('p', 'helper', `Chunk ${c.position + 1} · Page ${c.page} · Characters ${c.start}–${c.end}`), el('pre', '', c.text)); });
        $('chunk-dialog').showModal();
      } catch (e) { notice(e.message); }
    };
    const remove = el('button', 'text-button delete', 'Remove'); remove.setAttribute('aria-label', `Remove ${d.name}`);
    remove.onclick = async () => {
      if (!confirm(`Remove ${d.name} and its indexed chunks? You can upload the file again.`)) return;
      try { await api(`/api/documents/${d.id}`, {method: 'DELETE'}); selected.delete(d.id); await loadDocuments(); } catch (e) { notice(e.message); }
    };
    actions.append(view, remove); row.append(actions); $('documents').append(row);
  });
}
async function uploadFiles(files) {
  $('upload').disabled = true;
  try {
    for (const file of files) {
      $('upload-status').textContent = `Indexing ${file.name}… First upload downloads the embedding model.`;
      const form = new FormData(); form.append('file', file);
      const result = await api('/api/documents', {method: 'POST', body: form});
      $('upload-status').textContent = `${result.name}: ${result.chunks} chunks ${result.created ? 'indexed' : 'already indexed'}.`;
    }
    await loadDocuments();
  } catch (e) { notice(e.message); $('upload-status').textContent = 'Upload failed. See the message above.'; }
  finally { $('upload').disabled = false; $('upload').value = ''; }
}
async function newSession() {
  const session = await api('/api/sessions', {method: 'POST'}); sessionId = session.id; localStorage.setItem('relay-session', sessionId);
}
$('chat-form').onsubmit = async event => {
  event.preventDefault(); if (busy || !$('query').value.trim()) return;
  const query = $('query').value.trim();
  try {
    setBusy(true); const result = await api('/api/runs', post({query, session_id: sessionId, top_k: Number($('top-k').value), document_ids: [...selected]}));
    resetTrace(); tab(false); addMessage('user', query); $('query').value = ''; $('run-status').textContent = 'Queued for the supervisor…'; watchRun(result.id);
  } catch (e) { setBusy(false); notice(e.message); }
};
$('query').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('chat-form').requestSubmit(); } };
document.querySelectorAll('[data-prompt]').forEach(button => { button.onclick = () => { $('query').value = button.dataset.prompt; $('query').focus(); }; });
$('top-k').oninput = () => { $('top-k-value').textContent = $('top-k').value; };
$('upload').onchange = e => uploadFiles([...e.target.files]);
$('dropzone').onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('upload').click(); } };
$('dropzone').ondragover = e => { e.preventDefault(); $('dropzone').classList.add('drag'); };
$('dropzone').ondragleave = () => $('dropzone').classList.remove('drag');
$('dropzone').ondrop = e => { e.preventDefault(); $('dropzone').classList.remove('drag'); if (!$('upload').disabled) uploadFiles([...e.dataTransfer.files]); };
$('refresh').onclick = () => loadDocuments().catch(e => notice(e.message));
$('close-dialog').onclick = () => $('chunk-dialog').close();
$('tab-agents').onclick = () => tab(false); $('tab-sources').onclick = () => tab(true);
$('new-chat').onclick = async () => { try { await newSession(); $('messages').replaceChildren(); addMessage('assistant', 'New conversation started. Your document library is ready.'); resetTrace(); $('run-status').textContent = 'Ready when you are'; $('query').focus(); } catch (e) { notice(e.message); } };
$('connection').onclick = async () => {
  $('connection').disabled = true; $('connection').textContent = 'Connecting…';
  try { const result = await api('/api/provider/check', {method: 'POST'}); notice(`Connected to EURI. Provider returned model: ${result.model}.`, true); }
  catch (e) { notice(e.message); } finally { $('connection').disabled = false; $('connection').textContent = 'Check connection'; }
};
$('export').onclick = () => {
  if (!lastRun) return; const url = URL.createObjectURL(new Blob([JSON.stringify(lastRun, null, 2)], {type: 'application/json'}));
  const link = el('a'); link.href = url; link.download = `relay-run-${lastRun.id}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
async function init() {
  resetTrace(); setBusy(true);
  try {
    const [health] = await Promise.all([api('/api/health'), loadDocuments()]);
    $('model-label').textContent = `${health.model} / EURI`;
    if (!health.configured) notice('Add EURI_API_KEY to your local .env file and restart the server to enable live answers. Document uploads work independently.');
    let history = [];
    if (sessionId) { try { history = await api(`/api/sessions/${sessionId}/messages`); } catch { sessionId = null; } }
    if (!sessionId) await newSession();
    history.forEach(m => addMessage(m.role, m.content, m.run_id));
    const pending = localStorage.getItem('relay-active-run');
    if (pending) {
      const run = await api(`/api/runs/${pending}`);
      if (run.session_id === sessionId) {
        if (['queued', 'running'].includes(run.status)) { addMessage('user', run.query); watchRun(pending); return; }
        completeRun(run, !history.some(m => m.run_id === pending));
      } else localStorage.removeItem('relay-active-run');
    }
  } catch (e) { notice(`Application initialization failed: ${e.message}`); }
  setBusy(false);
}
init();
